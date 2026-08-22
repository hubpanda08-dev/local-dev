-- Manually applies V20260821073441__cargo__metadata_farm_concurrent.sql's effect and records it
-- as done in app_cargo.flyway_schema_history, local-dev-only.
--
-- Why: same structural deadlock as apply-pending-cargo-migration.sql — CREATE/DROP INDEX
-- CONCURRENTLY cannot run inside Flyway's own held transaction. The target table is empty in
-- this local dev DB, so plain (non-concurrent) CREATE/DROP INDEX is functionally equivalent and
-- instant — no long-lived lock risk here.

SET search_path TO app_cargo;

DO $onf_dropix$
DECLARE _con text; _tbl text;
BEGIN
  SELECT con.conname, rel.relname INTO _con, _tbl
  FROM pg_class ix
  JOIN pg_namespace nsp ON nsp.oid = ix.relnamespace
  JOIN pg_constraint con ON con.conindid = ix.oid AND con.contype = 'u'
  JOIN pg_class rel ON rel.oid = con.conrelid
  WHERE ix.relname = 'idx_document_payload_gin' AND nsp.nspname = current_schema();
  IF _con IS NOT NULL THEN
    EXECUTE format('ALTER TABLE %I.%I DROP CONSTRAINT %I', current_schema(), _tbl, _con);
  END IF;
END
$onf_dropix$;
DROP INDEX IF EXISTS idx_document_payload_gin;
CREATE INDEX IF NOT EXISTS idx_document_payload_gin ON cargo_document USING gin (document_details);

INSERT INTO app_cargo.flyway_schema_history
    (installed_rank, version, description, type, script, checksum, installed_by, execution_time, success)
SELECT
    (SELECT COALESCE(MAX(installed_rank), 0) + 1 FROM app_cargo.flyway_schema_history),
    '20260821073441', 'cargo metadata farm concurrent', 'SQL',
    'V20260821073441__cargo__metadata_farm_concurrent.sql',
    0, 'postgres', 0, true
WHERE NOT EXISTS (
    SELECT 1 FROM app_cargo.flyway_schema_history WHERE version = '20260821073441'
);
