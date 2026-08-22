-- Manually applies V20260817131155__cargo__metadata_farm_concurrent.sql's effect and records it
-- as done in app_cargo.flyway_schema_history, local-dev-only.
--
-- Why: same structural deadlock as apply-pending-cargo-migration.sql (see that file for the full
-- explanation) — this migration's CREATE/DROP INDEX CONCURRENTLY statements cannot run inside a
-- transaction, but Flyway's own schema-history bookkeeping connection holds one open for the
-- duration of migrate(), through vault-tenant's per-tenant DataSource. Confirmed stuck: pid running
-- Flyway's own history SELECT (idle in transaction, holding the advisory lock) blocking the
-- CONCURRENTLY DDL on a separate connection, which in turn never lets the first transaction close.
--
-- All 5 target tables are empty in this local dev DB, so plain (non-concurrent) CREATE/DROP INDEX
-- is functionally equivalent and instant — no long-lived lock risk here.

DROP INDEX IF EXISTS app_cargo.uq_rate_card_code_active;
CREATE UNIQUE INDEX IF NOT EXISTS uq_rate_card_code_active ON app_cargo.cargo_transporter_rate_card (tenant_id, code) WHERE (deleted_at IS NULL AND is_active = true);

DROP INDEX IF EXISTS app_cargo.uq_transporter_rate_card_code;
CREATE UNIQUE INDEX IF NOT EXISTS uq_transporter_rate_card_code ON app_cargo.cargo_transporter_rate_card (tenant_id, rate_card_code) WHERE (deleted_at IS NULL AND is_active = true);

DROP INDEX IF EXISTS app_cargo.uq_sla_policy_code_active;
CREATE UNIQUE INDEX IF NOT EXISTS uq_sla_policy_code_active ON app_cargo.cargo_transporter_sla_policy (tenant_id, code) WHERE (deleted_at IS NULL AND is_active = true);

DROP INDEX IF EXISTS app_cargo.uq_transporter_sla_policy_code;
CREATE UNIQUE INDEX IF NOT EXISTS uq_transporter_sla_policy_code ON app_cargo.cargo_transporter_sla_policy (tenant_id, sla_policy_code) WHERE (deleted_at IS NULL AND is_active = true);

DROP INDEX IF EXISTS app_cargo.idx_osfieldcfg_tenant;
CREATE INDEX IF NOT EXISTS idx_osfieldcfg_tenant ON app_cargo.opensearch_field_config (tenant_id);

DROP INDEX IF EXISTS app_cargo.uq_cargo_trip_event_last_op;
CREATE UNIQUE INDEX IF NOT EXISTS uq_cargo_trip_event_last_op ON app_cargo.cargo_trip_event (tenant_id, last_operation_id) WHERE (deleted_at IS NULL AND last_operation_id IS NOT NULL);

INSERT INTO app_cargo.flyway_schema_history
    (installed_rank, version, description, type, script, checksum, installed_by, execution_time, success)
SELECT
    (SELECT COALESCE(MAX(installed_rank), 0) + 1 FROM app_cargo.flyway_schema_history),
    '20260817131155', 'cargo  metadata farm concurrent', 'SQL',
    'V20260817131155__cargo__metadata_farm_concurrent.sql',
    0, 'postgres', 0, true
WHERE NOT EXISTS (
    SELECT 1 FROM app_cargo.flyway_schema_history WHERE version = '20260817131155'
);
