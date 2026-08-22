-- Local-dev-only sample data for app_cargo, tenant "beta" (352f9f27-83a3-42d3-b3d0-44e72ac807f9).
-- Direct SQL seed (not run through the API) so cargo's read/list/get endpoints have something to
-- return without needing master-data/identity fully wired for FK-validated creation.
-- Safe to re-run: guarded by the same unique (tenant_id, code) constraints via ON CONFLICT DO NOTHING.

\set tenant_id '352f9f27-83a3-42d3-b3d0-44e72ac807f9'
\set created_by '0d6676c2-38ad-4d88-8938-222dcd026a74'

INSERT INTO app_cargo.cargo_shipment (
    id, public_id, code, tenant_id, kind, direction, priority,
    total_weight_kg, hazmat_flag, cold_chain_flag, lifecycle_state,
    origin_location_name, destination_location_name, consignor_name,
    vehicle_type_code, created_by, updated_by
) VALUES (
    gen_random_uuid(), 'shp_devseed0001', 'SHP-DEV-0001', :'tenant_id'::uuid, 'FTL', 'OUTBOUND', 'NORMAL',
    5000.00, false, false, 'PUBLISHED',
    'Bhiwandi Warehouse, Maharashtra', 'Whitefield Hub, Bengaluru', 'Acme Logistics Pvt Ltd',
    '32FT_MXL', :'created_by'::uuid, :'created_by'::uuid
) ON CONFLICT (tenant_id, code) DO NOTHING
RETURNING id AS shipment_id \gset

-- \gset only sets shipment_id when the INSERT actually returned a row (fresh insert). Re-running
-- this script after the first time needs the existing row's id instead — look it up either way.
SELECT id AS shipment_id, public_id AS shipment_public_id
FROM app_cargo.cargo_shipment WHERE tenant_id = :'tenant_id'::uuid AND code = 'SHP-DEV-0001' \gset

INSERT INTO app_cargo.cargo_transporter_contract (
    id, public_id, code, tenant_id, contract_type, valid_from, valid_to,
    currency, status, contract_name, created_by, updated_by
) VALUES (
    gen_random_uuid(), 'con_devseed0001', 'CON-DEV-0001', :'tenant_id'::uuid, 'STANDARD',
    CURRENT_DATE, CURRENT_DATE + INTERVAL '1 year',
    'INR', 'ACTIVE', 'Fast Carriers Pvt Ltd — Standard Rate Contract', :'created_by'::uuid, :'created_by'::uuid
) ON CONFLICT (tenant_id, code) DO NOTHING;

INSERT INTO app_cargo.cargo_trip (
    id, public_id, code, tenant_id, primary_shipment_id, shipment_public_id,
    lifecycle_state, source_mode,
    origin_location_name, destination_location_name,
    assigned_vehicle_reg_no, assigned_driver_name, assigned_driver_phone,
    vehicle_type_code, created_by, updated_by
) VALUES (
    gen_random_uuid(), 'trp_devseed0001', 'TRP-DEV-0001', :'tenant_id'::uuid, :'shipment_id'::uuid, :'shipment_public_id',
    'planned', 'online',
    'Bhiwandi Warehouse, Maharashtra', 'Whitefield Hub, Bengaluru',
    'MH-04-AB-1234', 'Ramesh Kumar', '9876543210',
    '32FT_MXL', :'created_by'::uuid, :'created_by'::uuid
) ON CONFLICT (tenant_id, code) DO NOTHING;

SELECT 'shipment' AS entity, public_id, code, lifecycle_state FROM app_cargo.cargo_shipment WHERE tenant_id = :'tenant_id'::uuid
UNION ALL
SELECT 'trip', public_id, code, lifecycle_state FROM app_cargo.cargo_trip WHERE tenant_id = :'tenant_id'::uuid
UNION ALL
SELECT 'transporter_contract', public_id, code, status FROM app_cargo.cargo_transporter_contract WHERE tenant_id = :'tenant_id'::uuid;
