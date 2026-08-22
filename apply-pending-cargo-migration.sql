-- Manually applies V20260813105339__cargo__metadata_farm_concurrent.sql's effect and records it
-- as done in app_cargo.flyway_schema_history, local-dev-only.
--
-- Why: this migration uses CREATE/DROP INDEX CONCURRENTLY, which cannot run inside a transaction.
-- Flyway's own schema-history bookkeeping connection holds a transaction open for the duration of
-- migrate(), and CONCURRENTLY DDL on a separate connection must wait for that transaction (and
-- every other open transaction) to finish before it can proceed — a structural deadlock between
-- Flyway's own connections through vault-tenant's per-tenant DataSource. Every cargo request that
-- triggers this pending migration hangs forever (confirmed: single clean request, no concurrent
-- callers, still deadlocks after 300s). validate-on-migrate is false in cargo's config, so a
-- checksum mismatch here is harmless — this only needs to make Flyway see the version as applied.
--
-- The target table is empty in this local dev DB, so a plain (non-concurrent) CREATE INDEX is
-- functionally equivalent and instant — no long-lived lock risk here.

CREATE INDEX IF NOT EXISTS idx_auto_quote_rule_owner ON app_cargo.cargo_auto_quote_rule (owner_user_id);
CREATE INDEX IF NOT EXISTS idx_share_of_business_rule_owner ON app_cargo.cargo_share_of_business_rule (owner_user_id);
CREATE INDEX IF NOT EXISTS idx_waterfall_custom_config_owner ON app_cargo.cargo_waterfall_custom_config (owner_user_id);
CREATE INDEX IF NOT EXISTS idx_ccsl_owner_user_id ON app_cargo.cargo_connect_settlement_line (owner_user_id);
CREATE INDEX IF NOT EXISTS idx_cargo_connect_trip_charge_owner ON app_cargo.cargo_connect_trip_charge (owner_user_id);

INSERT INTO app_cargo.flyway_schema_history
    (installed_rank, version, description, type, script, checksum, installed_by, execution_time, success)
SELECT
    (SELECT COALESCE(MAX(installed_rank), 0) + 1 FROM app_cargo.flyway_schema_history),
    '20260813105339', 'cargo  metadata farm concurrent', 'SQL',
    'V20260813105339__cargo__metadata_farm_concurrent.sql',
    0, 'postgres', 0, true
WHERE NOT EXISTS (
    SELECT 1 FROM app_cargo.flyway_schema_history WHERE version = '20260813105339'
);
