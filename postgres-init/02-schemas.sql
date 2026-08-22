-- Per-service schemas inside `onified_beta_local`.
-- Names match the beta backup structure and each service's application-local.yml.
-- Each service's Flyway migrations (or the beta pg_restore) populate the tables;
-- we only create the schema namespace so services can connect cleanly on a
-- fresh containerized Postgres.
--
-- POSTGRES_DB=onified_beta_local in docker-compose.local.yml means we're already
-- connected to that DB when this script runs — no \connect needed.

CREATE SCHEMA IF NOT EXISTS platform_gateway_service;       -- gateway
CREATE SCHEMA IF NOT EXISTS iam;                             -- identity + sso (shared)
CREATE SCHEMA IF NOT EXISTS platform_content;               -- content
CREATE SCHEMA IF NOT EXISTS data_platform_service;          -- platform-data
CREATE SCHEMA IF NOT EXISTS platform_analytics;             -- analytics
CREATE SCHEMA IF NOT EXISTS platform_billing_service;       -- billing-subscription
CREATE SCHEMA IF NOT EXISTS platform_governance_service;    -- governance
CREATE SCHEMA IF NOT EXISTS platform_notification_service;  -- notification
CREATE SCHEMA IF NOT EXISTS platform_integration_service;   -- integration
CREATE SCHEMA IF NOT EXISTS platform_job_orchestration;     -- job-orchestration
CREATE SCHEMA IF NOT EXISTS platform_work_management;       -- work-management
CREATE SCHEMA IF NOT EXISTS platform_workflow_service;      -- workflow
CREATE SCHEMA IF NOT EXISTS platform_geo;                   -- geo
-- master-data and cargo: no schema set in their application-local.yml; fall through
-- to `public`. They can still connect — Hibernate will use the search_path default.
