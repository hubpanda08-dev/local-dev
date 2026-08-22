-- Local-dev-only fix: app_cargo.cargo_exception in this DB carries legacy columns (title NOT
-- NULL, reported_by) that predate the current CargoException entity/migrations. Neither column is
-- tracked by any migration in services/apps/cargo/src/main/resources/db/migration/ or mapped by
-- the JPA entity (onified.ai.cargo.exceptions.entity.CargoException) — confirmed by grep across
-- all migration files. Flyway's `ADD COLUMN IF NOT EXISTS` never corrects a pre-existing column's
-- constraints, so this local table was left stuck with the old shape. Every exception create fails
-- with "null value in column title violates not-null constraint" until this is dropped.
--
-- This is local-environment drift only — a fresh DB built from the current migrations would never
-- have a `title` column on this table, so there is nothing to fix upstream in the migration files.

ALTER TABLE app_cargo.cargo_exception ALTER COLUMN title DROP NOT NULL;

-- Also drop legacy CHECK constraints from the same old table incarnation, which conflict with the
-- current farm-generated ones on the same table (a row must satisfy every constraint present):
--   chk_exception_severity        — required UPPERCASE values (LOW/MEDIUM/HIGH/CRITICAL), current
--                                    entity/constraint (cargo_exception_severity_check) uses lowercase.
--   chk_exception_status          — an entirely different, older status vocabulary
--                                    (open/acknowledged/in_progress/resolved/closed/escalated) vs.
--                                    current (flagged/in_review/escalated/resolved/waived/closed/duplicate).
--   chk_exception_kind            — functionally identical duplicate of cargo_exception_exception_kind_check.
--   chk_exception_resolution_kind — functionally identical duplicate of cargo_exception_resolution_kind_check.
-- None of these four are referenced by any migration file — pure local drift from before the table
-- was redesigned. Superseded by the "cargo_exception_*_check" constraints, which stay.

ALTER TABLE app_cargo.cargo_exception DROP CONSTRAINT IF EXISTS chk_exception_severity;
ALTER TABLE app_cargo.cargo_exception DROP CONSTRAINT IF EXISTS chk_exception_status;
ALTER TABLE app_cargo.cargo_exception DROP CONSTRAINT IF EXISTS chk_exception_kind;
ALTER TABLE app_cargo.cargo_exception DROP CONSTRAINT IF EXISTS chk_exception_resolution_kind;
