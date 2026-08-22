"""Mock TRIDENT server.

Implements the Onified <-> TRIDENT integration spec exactly (Part 1 master-data
query contract for CUSTOMER/VENDOR/LANE/ADDRESS/CONTACT, Part 2 shipment +
gate-event reads, and the shipment.created push back into Onified) so
integration-service can be exercised end-to-end against something that
behaves like the real partner, without real tenant credentials.

Seed data is loaded at startup (see SEED below) — no external DB, no manual
seeding step needed before a test run.
"""
import hashlib
import hmac
import json
import os
import time
import uuid
from datetime import datetime, timezone
from typing import Optional

import httpx
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse

BEARER_TOKEN = os.environ.get("TRIDENT_BEARER_TOKEN", "trident-dev-token")
ONIFIED_SIGNING_SECRET = os.environ.get("ONIFIED_SIGNING_SECRET", "dev-shared-secret")
ONIFIED_INGRESS_URL = os.environ.get("ONIFIED_INGRESS_URL", "")
ONIFIED_INGRESS_TOKEN = os.environ.get("ONIFIED_INGRESS_TOKEN", "")
PAGE_SIZE_DEFAULT = 500

ENTITIES = ["CUSTOMER", "VENDOR", "LANE", "ADDRESS", "CONTACT"]

app = FastAPI(title="mock-trident")


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ── In-memory state, preloaded with seed data ───────────────────────────────
db = {e: {} for e in ENTITIES}
shipments: dict[str, dict] = {}
gate_events: dict[str, list] = {}
cursors: dict[str, dict] = {}
chaos = {"rate_limited": False, "force_not_found": False}


def seed(entity: str, record: dict):
    db[entity][record["externalRefCode"]] = {**record, "_updatedAt": now_iso()}


seed("CUSTOMER", {
    "externalRefCode": "CUST-00112", "externalRefId": "8842103",
    "customerName": "Acme Distribution Pvt Ltd", "displayName": "Acme",
    "customerTypeCode": "OEM", "taxIdentifier": "27ACMEE1234F1Z5",
    "currencyCode": "INR", "creditLimit": 500000.00, "accountStatus": "ACTIVE",
    "contactPersonName": "Rakesh Sharma", "contactEmail": "rakesh@acme.example",
    "contactPhone": "+919812345678",
})
seed("VENDOR", {
    "externalRefCode": "VEND-0042", "externalRefId": "7712004",
    "vendorName": "Bharat Freight Carriers", "displayName": "Bharat Freight",
    "vendorTypeCode": "TRANSPORTER", "taxIdentifier": "07BFCPL5678G1Z2",
    "currencyCode": "INR", "complianceStatus": "ACTIVE",
    "contactPersonName": "Suresh Iyer", "contactEmail": "suresh@bfc.example",
    "contactPhone": "+919887654321",
})
seed("LANE", {
    "externalRefCode": "LANE-BUD-DEL", "externalRefId": "5501",
    "laneName": "Budaun - Delhi", "laneTypeCode": "PRIMARY",
    "description": "Primary corridor Budaun plant to Delhi warehouse",
    "standardDistanceKm": 210.5, "standardTransitTimeMinutes": 420,
    "status": "ACTIVE",
})
seed("ADDRESS", {
    "externalRefCode": "ADDR-00998", "externalRefId": "9001",
    "ownerEntityType": "CUSTOMER", "ownerExternalRefCode": "CUST-00112",
    "addressType": "SHIPPING", "status": "ACTIVE",
    "line1": "Plot 14, Industrial Area", "line2": None, "line3": None,
    "city": "Budaun", "district": "Budaun", "stateProvince": "Uttar Pradesh",
    "postalCode": "243601", "countryCode": "IN",
})
seed("CONTACT", {
    "externalRefCode": "CONT-00551", "externalRefId": "3301",
    "ownerEntityType": "CUSTOMER", "ownerExternalRefCode": "CUST-00112",
    "contactName": "Rakesh Sharma", "contactRoleCode": "OPERATIONS",
    "status": "ACTIVE", "mobile": "+919812345678", "alternateMobile": None,
    "email": "rakesh@acme.example", "alternateEmail": None,
    "primaryChannelCode": "WHATSAPP", "secondaryChannelCode": "EMAIL",
    "designation": "Logistics Manager", "department": "Supply Chain",
    "companyName": "Acme Distribution Pvt Ltd", "isPrimary": True,
    "remarks": None,
})
shipments["SHIP-0004471"] = {
    "externalRefCode": "SHIP-0004471", "externalRefId": "8842103",
    "status": "OPEN", "requiredVehicleTime": "2026-07-26T14:00:00+05:30",
    "vehicleTypeCode": "TRK32", "originCode": "PLANT_BUD",
    "destinationCode": "WH_DEL", "customerExternalRefCode": "CUST-00112",
    "laneExternalRefCode": "LANE-BUD-DEL", "remarks": None,
}
gate_events["SHIP-0004471"] = []


def error_body(code: str, message: str, retryable: bool):
    return {"error": {"code": code, "message": message, "retryable": retryable}}


def check_bearer(authorization: Optional[str]):
    if authorization != f"Bearer {BEARER_TOKEN}":
        raise HTTPException(status_code=401, detail=error_body("AUTH_FAILED", "Missing or invalid bearer token", False))


def check_chaos():
    if chaos["rate_limited"]:
        raise HTTPException(status_code=429, detail=error_body("RATE_LIMITED", "Too many requests, retry after backoff", True))


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    body = exc.detail if isinstance(exc.detail, dict) else {"error": {"code": "ERROR", "message": str(exc.detail), "retryable": False}}
    return JSONResponse(status_code=exc.status_code, content=body)


# ── Part 1.3: POST /{entity}/query ──────────────────────────────────────────
@app.post("/{entity}/query")
async def query(entity: str, request: Request, authorization: Optional[str] = Header(None)):
    check_bearer(authorization)
    entity = entity.upper()
    if entity not in ENTITIES:
        raise HTTPException(status_code=400, detail=error_body("ENTITY_NOT_SUPPORTED", f"Unknown entity {entity}", False))
    check_chaos()

    body = await request.json()
    sync_mode = body.get("syncMode")
    changed_from = body.get("changedFrom")
    cursor = body.get("cursor")
    limit = body.get("limit") or PAGE_SIZE_DEFAULT
    store = db[entity]
    requested_at = now_iso()

    meta = None
    if cursor:
        state = cursors.get(cursor)
        if not state or state["entity"] != entity:
            raise HTTPException(status_code=400, detail=error_body("INVALID_CURSOR", "Unknown or expired cursor", False))
        ids = state["ids"]
        offset = state["offset"]
        meta = state["meta"]
    else:
        if sync_mode == "DELTA":
            from_ts = changed_from or "1970-01-01T00:00:00Z"
            ids = [code for code, rec in store.items() if rec["_updatedAt"] >= from_ts]
            meta = {"changedFrom": from_ts, "changedTo": requested_at}
        else:
            ids = list(store.keys())
        offset = 0

    page = ids[offset: offset + limit]
    has_more = offset + limit < len(ids)
    next_cursor = None
    if has_more:
        next_cursor = f"cur_{entity}_{uuid.uuid4().hex[:8]}"
        cursors[next_cursor] = {"entity": entity, "ids": ids, "offset": offset + limit, "meta": meta}

    records = []
    for code in page:
        rec = dict(store[code])
        rec.pop("_updatedAt", None)
        records.append(rec)

    result = {"hasMore": has_more, "nextCursor": next_cursor, "data": {"records": records}}
    if sync_mode == "DELTA":
        result["meta"] = meta
    return result


# ── Part 2.2: GET /shipments/{code} ─────────────────────────────────────────
@app.get("/shipments/{code}")
async def get_shipment(code: str, authorization: Optional[str] = Header(None)):
    check_bearer(authorization)
    check_chaos()
    shipment = shipments.get(code)
    if not shipment or chaos["force_not_found"]:
        raise HTTPException(status_code=404, detail=error_body("NOT_FOUND", "Unknown shipment code", False))
    return shipment


# ── Part 2.3: GET /gate-events/{code} ───────────────────────────────────────
@app.get("/gate-events/{code}")
async def get_gate_events(code: str, authorization: Optional[str] = Header(None)):
    check_bearer(authorization)
    check_chaos()
    if code not in shipments:
        raise HTTPException(status_code=404, detail=error_body("NOT_FOUND", "Unknown shipment code", False))
    return {"shipmentExternalRefCode": code, "events": gate_events.get(code, [])}


# ── Admin/control API — NOT part of the TRIDENT spec. Drives test scenarios: ─
@app.post("/_admin/seed/{entity}")
async def admin_seed(entity: str, request: Request):
    entity = entity.upper()
    if entity not in ENTITIES:
        raise HTTPException(status_code=400, detail={"error": "unknown entity"})
    record = await request.json()
    if "externalRefCode" not in record:
        raise HTTPException(status_code=400, detail={"error": "externalRefCode required"})
    seed(entity, record)
    return {"ok": True}


@app.post("/_admin/shipments")
async def admin_add_shipment(request: Request):
    shipment = await request.json()
    if "externalRefCode" not in shipment:
        raise HTTPException(status_code=400, detail={"error": "externalRefCode required"})
    shipments[shipment["externalRefCode"]] = shipment
    gate_events[shipment["externalRefCode"]] = []
    return {"ok": True}


@app.post("/_admin/gate-events/{code}")
async def admin_add_gate_event(code: str, request: Request):
    if code not in shipments:
        raise HTTPException(status_code=404, detail={"error": "unknown shipment code"})
    event = await request.json()
    gate_events[code].append({"type": event["type"], "time": event.get("time") or now_iso()})
    return {"ok": True}


@app.post("/_admin/chaos")
async def admin_chaos(request: Request):
    chaos.update(await request.json())
    return chaos


@app.post("/_admin/reset")
async def admin_reset():
    for e in ENTITIES:
        db[e].clear()
    shipments.clear()
    gate_events.clear()
    cursors.clear()
    chaos.update({"rate_limited": False, "force_not_found": False})
    return {"ok": True}


@app.post("/_admin/trigger-shipment-created")
async def trigger_shipment_created(request: Request):
    if not ONIFIED_INGRESS_URL:
        raise HTTPException(status_code=500, detail={"error": "ONIFIED_INGRESS_URL not configured"})
    body = await request.json()
    shipment_code = body.get("shipmentExternalRefCode")
    if not shipment_code:
        raise HTTPException(status_code=400, detail={"error": "shipmentExternalRefCode required"})

    event_id = body.get("id") or f"evt_{uuid.uuid4()}"
    payload = {
        "id": event_id,
        "type": "shipment.created",
        "time": now_iso(),
        "data": {"shipmentExternalRefCode": shipment_code},
    }
    raw = json.dumps(payload, separators=(",", ":")).encode()
    signature = "sha256=" + hmac.new(ONIFIED_SIGNING_SECRET.encode(), raw, hashlib.sha256).hexdigest()
    timestamp = str(int(time.time()))

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            ONIFIED_INGRESS_URL,
            content=raw,
            headers={
                "Content-Type": "application/json",
                "X-Onified-Signature": signature,
                "X-Onified-Timestamp": timestamp,
                "Authorization": f"Bearer {ONIFIED_INGRESS_TOKEN}",
            },
        )
    return {"sent": payload, "onifiedStatus": resp.status_code, "onifiedBody": resp.text}


@app.get("/_admin/health")
async def health():
    return {"ok": True}
