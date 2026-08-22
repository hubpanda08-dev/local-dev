-- Manually applies V20260818071535__cargo__metadata_farm_concurrent.sql's effect and records it
-- as done in app_cargo.flyway_schema_history, local-dev-only.
--
-- Why: same structural deadlock as apply-pending-cargo-migration.sql (see that file for the full
-- explanation) — CREATE/DROP INDEX CONCURRENTLY cannot run inside Flyway's own held transaction.
-- Confirmed stuck: the first live cargo request hung for 2+ minutes with Flyway's history-read
-- connection idle-in-transaction and a separate connection blocked on
-- "CREATE UNIQUE INDEX CONCURRENTLY ... uq_carrier_contract_code_active ... ON cargo_transporter_contract".
--
-- Both target tables are empty in this local dev DB, so plain (non-concurrent) CREATE/DROP INDEX
-- is functionally equivalent and instant — no long-lived lock risk here.

SET search_path TO app_cargo;

DO $onf_dropix$
DECLARE _con text; _tbl text;
BEGIN
  SELECT con.conname, rel.relname INTO _con, _tbl
  FROM pg_class ix
  JOIN pg_namespace nsp ON nsp.oid = ix.relnamespace
  JOIN pg_constraint con ON con.conindid = ix.oid AND con.contype = 'u'
  JOIN pg_class rel ON rel.oid = con.conrelid
  WHERE ix.relname = 'uq_carrier_contract_code_active' AND nsp.nspname = current_schema();
  IF _con IS NOT NULL THEN
    EXECUTE format('ALTER TABLE %I.%I DROP CONSTRAINT %I', current_schema(), _tbl, _con);
  END IF;
END
$onf_dropix$;
DROP INDEX IF EXISTS uq_carrier_contract_code_active;
CREATE UNIQUE INDEX IF NOT EXISTS uq_carrier_contract_code_active ON cargo_transporter_contract (tenant_id, code) WHERE (deleted_at IS NULL AND is_active = true);

DO $onf_dropix$
DECLARE _con text; _tbl text;
BEGIN
  SELECT con.conname, rel.relname INTO _con, _tbl
  FROM pg_class ix
  JOIN pg_namespace nsp ON nsp.oid = ix.relnamespace
  JOIN pg_constraint con ON con.conindid = ix.oid AND con.contype = 'u'
  JOIN pg_class rel ON rel.oid = con.conrelid
  WHERE ix.relname = 'uq_cargo_trip_last_op' AND nsp.nspname = current_schema();
  IF _con IS NOT NULL THEN
    EXECUTE format('ALTER TABLE %I.%I DROP CONSTRAINT %I', current_schema(), _tbl, _con);
  END IF;
END
$onf_dropix$;
DROP INDEX IF EXISTS uq_cargo_trip_last_op;
CREATE UNIQUE INDEX IF NOT EXISTS uq_cargo_trip_last_op ON cargo_trip (tenant_id, last_operation_id) WHERE (last_operation_id IS NOT NULL AND deleted_at IS NULL);

INSERT INTO app_cargo.flyway_schema_history
    (installed_rank, version, description, type, script, checksum, installed_by, execution_time, success)
SELECT
    (SELECT COALESCE(MAX(installed_rank), 0) + 1 FROM app_cargo.flyway_schema_history),
    '20260818071535', 'cargo metadata farm concurrent', 'SQL',
    'V20260818071535__cargo__metadata_farm_concurrent.sql',
    0, 'postgres', 0, true
WHERE NOT EXISTS (
    SELECT 1 FROM app_cargo.flyway_schema_history WHERE version = '20260818071535'
);
