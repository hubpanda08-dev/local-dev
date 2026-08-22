-- Local-dev-only fix: re-adds app_cargo.outbox_event.trace_id, which a farm-generated migration
-- incorrectly dropped.
--
-- Root cause: V20260807051442__cargo__metadata_farm.sql ADDs outbox_event.trace_id (needed by the
-- shared outbox-spring-boot-starter library's own INSERT, written via raw JDBC, not JPA-mapped).
-- A later migration, V20260811165845__cargo__metadata_farm.sql, DROPs the same column
-- ("Dropping deleted column trace_id") because the metadata farm's manifest never tracks it (it's
-- not a JPA-annotated field on any farm-managed entity) — the farm's reconciliation sees an
-- untracked column and removes it, even though the library still writes to it unconditionally on
-- every event publish. Confirmed reproducible: any cargo event publish (old or new) 500s with
-- "column trace_id of relation outbox_event does not exist" until this is re-applied.
--
-- This is a workaround for local testing, not a real fix — re-running the metadata farm here will
-- drop the column again. The actual fix belongs upstream (exclude outbox_event from farm
-- reconciliation, or register trace_id so the farm stops treating it as orphaned) and is out of
-- scope for this repo's editing restrictions (farm-generated migrations are DO-NOT-EDIT).

ALTER TABLE app_cargo.outbox_event ADD COLUMN IF NOT EXISTS trace_id VARCHAR(64);
