import pandas as pd
import psycopg2
import math
import sys

SRC_DIR = r"C:\Users\windo\Downloads\Downloads\Downloads"
OLD_TENANT = "cbfb46e2-77ee-4b80-b3e6-1e50f477bfd2"
NEW_TENANT = "352f9f27-83a3-42d3-b3d0-44e72ac807f9"

conn = psycopg2.connect(
    host="localhost", port=5432, dbname="onified_beta_local",
    user="postgres", password="Thekapilg",
)
conn.autocommit = False
cur = conn.cursor()
cur.execute("SET app.current_tenant_id = %s", (NEW_TENANT,))

DATE_LIKE_SUFFIXES = ("_at", "_from", "_to", "_date")

def clean(v, col=None):
    if v is None:
        return None
    if isinstance(v, float) and math.isnan(v):
        return None
    try:
        if pd.isna(v):
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(v, pd.Timestamp):
        return v.to_pydatetime()
    # Some sheet rows have garbage in date-like columns (e.g. a UUID accidentally
    # left in deleted_at). Coerce anything that doesn't actually parse as a date
    # to None instead of letting Postgres reject the whole row.
    if col is not None and isinstance(v, str) and col.endswith(DATE_LIKE_SUFFIXES):
        parsed = pd.to_datetime(v, errors="coerce")
        if pd.isna(parsed):
            return None
        return parsed.to_pydatetime()
    return v

def table_columns(schema, table):
    cur.execute("""
        SELECT column_name FROM information_schema.columns
        WHERE table_schema=%s AND table_name=%s
    """, (schema, table))
    return {r[0] for r in cur.fetchall()}

def table_column_types(schema, table):
    cur.execute("""
        SELECT column_name, data_type FROM information_schema.columns
        WHERE table_schema=%s AND table_name=%s
    """, (schema, table))
    return {r[0]: r[1] for r in cur.fetchall()}

def existing_codes(schema, table):
    """code -> id for rows already present under NEW_TENANT."""
    cur.execute(f'SELECT code, id FROM {schema}.{table} WHERE tenant_id=%s', (NEW_TENANT,))
    return {r[0]: r[1] for r in cur.fetchall()}

def public_id_map(schema, table):
    """public_id -> id for rows already present under NEW_TENANT."""
    cur.execute(f'SELECT public_id, id FROM {schema}.{table} WHERE tenant_id=%s', (NEW_TENANT,))
    return {r[0]: r[1] for r in cur.fetchall()}

def load_sheet(file, sheet, schema, table, skip_cols=(), dedupe_by_code=False, id_remap=None):
    """
    id_remap: optional {col_name: {old_id: new_id}} applied to columns before insert
      (e.g. rewriting geofence_records.location_id to point at geo_locations rows
      that already existed locally under a different id).
    dedupe_by_code: if True, rows whose `code` already exists for NEW_TENANT are
      skipped (not re-inserted) and instead folded into the returned remap so
      downstream sheets referencing this table's id keep working.
    Returns (df, remap) where remap is {sheet_row_id: effective_db_id}.
    """
    df = file if isinstance(file, pd.DataFrame) else pd.read_excel(f"{SRC_DIR}\\{file}", sheet_name=sheet)
    if "tenant_id" in df.columns:
        df["tenant_id"] = df["tenant_id"].apply(lambda v: NEW_TENANT if v == OLD_TENANT else v)
    real_cols = table_columns(schema, table)
    col_types = table_column_types(schema, table)
    candidate_cols = [c for c in df.columns if c in real_cols and c not in skip_cols]
    dropped = [c for c in df.columns if c not in real_cols]

    existing = existing_codes(schema, table) if dedupe_by_code and "code" in df.columns else {}
    remap = {}
    inserted = 0
    skipped_existing = 0
    for _, row in df.iterrows():
        row_id = row.get("id")
        if pd.isna(row_id):
            continue  # blank trailer row (Excel artifact)
        code = row.get("code") if "code" in df.columns else None
        if code in existing:
            remap[row_id] = existing[code]
            skipped_existing += 1
            continue
        remap[row_id] = row_id

        pairs = [(c, clean(row[c], c)) for c in candidate_cols]
        if id_remap:
            pairs = [(c, id_remap[c].get(v, v) if c in id_remap and v is not None else v) for c, v in pairs]
        # Sheets sometimes store booleans as 0.0/1.0 floats; cast to the real column type.
        pairs = [(c, bool(v) if col_types.get(c) == "boolean" and isinstance(v, (int, float)) else v)
                 for c, v in pairs]
        # Omit (not just null out) columns whose value is missing so the table's
        # own DEFAULT applies — an explicit NULL would override the default and
        # trip NOT NULL constraints (e.g. aggregate_version) on partially blank rows.
        pairs = [(c, v) for c, v in pairs if v is not None]
        use_cols = [c for c, _ in pairs]
        values = [v for _, v in pairs]
        placeholders = ", ".join(["%s"] * len(use_cols))
        colnames = ", ".join(f'"{c}"' for c in use_cols)
        sql = f'INSERT INTO {schema}.{table} ({colnames}) VALUES ({placeholders}) ON CONFLICT DO NOTHING'
        cur.execute(sql, values)
        inserted += cur.rowcount
    print(f"[{schema}.{table}] rows_in_sheet={len(df)} inserted={inserted} "
          f"skipped_existing_by_code={skipped_existing} dropped_cols={dropped}")
    return df, remap

try:
    load_sheet("transporters.xlsx", "master_vendors", "platform_metadata_service", "master_vendors")
    load_sheet("master_customers.xlsx", "master_customers", "platform_metadata_service", "master_customers")
    load_sheet("master_addresses.xlsx", "master_address", "platform_metadata_service", "master_addresses")
    load_sheet("master_contacts.xlsx", "master_contacts", "platform_metadata_service", "master_contacts")
    load_sheet("master_lanes.xlsx", "master_lanes", "platform_metadata_service", "master_lanes")
    _, loc_remap = load_sheet("geo_locations.xlsx", "geo_locations", "geolocation", "geo_locations",
                               dedupe_by_code=True)

    load_sheet("master_lane_stops.xlsx", "master_lane_stops", "platform_metadata_service", "master_lane_stops",
               id_remap={"location_id": loc_remap})

    # geofence_records <-> geo_routes are mutually referencing; load geofence first
    # with route_id skipped, then geo_routes, then backfill route_id.
    gf_df, _ = load_sheet("geofence_records.xlsx", "geofence_records", "geolocation", "geofence_records",
                           skip_cols=("route_id",), id_remap={"location_id": loc_remap})
    load_sheet("GEO routes.xlsx", "geo_routes", "geolocation", "geo_routes")

    if "route_id" in gf_df.columns:
        backfilled = 0
        for _, row in gf_df.iterrows():
            rid = clean(row.get("route_id"))
            gid = clean(row.get("id"))
            if rid is not None and gid is not None:
                cur.execute(
                    "UPDATE geolocation.geofence_records SET route_id=%s WHERE id=%s AND route_id IS NULL",
                    (rid, gid),
                )
                backfilled += cur.rowcount
        print(f"[geolocation.geofence_records] route_id backfilled={backfilled}")

    vendor_pubid_map = public_id_map("platform_metadata_service", "master_vendors")
    load_sheet("cargo_carrier_contract.xlsx", "cargo_transporter_contract", "app_cargo", "cargo_transporter_contract",
               id_remap={"transporter_id": vendor_pubid_map})

    rate_card_df = pd.read_excel(f"{SRC_DIR}\\cargo_transorter_rate_card.xlsx", sheet_name="cargo_transporter_rate_card")
    # Sheet has both `code` (populated) and `rate_card_code` (blank) for the same
    # concept; the real table only kept `rate_card_code` and it's NOT NULL.
    rate_card_df["rate_card_code"] = rate_card_df["rate_card_code"].fillna(rate_card_df["code"])
    load_sheet(rate_card_df, None, "app_cargo", "cargo_transporter_rate_card")
    charge_rule_df = pd.read_excel(f"{SRC_DIR}\\cargo_transorter_rate_card.xlsx", sheet_name="cargo_contract_charge_rule")
    # Some rows have calculation_method blank and a non-numeric string (e.g. "FLAT")
    # left in rate_amount instead — clearly shifted source data. Repair: move that
    # string into calculation_method (a required text column) and null rate_amount.
    def _fix_charge_rule_row(r):
        cm, ra = r.get("calculation_method"), r.get("rate_amount")
        if pd.isna(cm) and isinstance(ra, str):
            r["calculation_method"] = ra
            r["rate_amount"] = None
        return r
    charge_rule_df = charge_rule_df.apply(_fix_charge_rule_row, axis=1)
    load_sheet(charge_rule_df, None, "app_cargo", "cargo_contract_charge_rule")
    load_sheet("detention_rule.xlsx", "cargo_transporter_detention_rul", "app_cargo", "cargo_contract_detention_rule")

    conn.commit()
    print("\nCOMMITTED")
except Exception as e:
    conn.rollback()
    print(f"\nROLLED BACK due to error: {e}", file=sys.stderr)
    raise
finally:
    cur.close()
    conn.close()
