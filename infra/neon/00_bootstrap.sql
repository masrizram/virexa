-- Neon bootstrap: run as the project owner (neon_superuser equivalent) via DIRECT connection.
-- Creates separate databases + least-privilege roles for Windmill and the business app.
-- Usage (after `neon connection-string` or from console psql):
--   psql "<DIRECT_URL_of_neondb>" -f infra/neon/00_bootstrap.sql
-- NOTE: on Neon, CREATE DATABASE must run connected to an existing DB (e.g. neondb);
-- roles are cluster-wide. CREATE ROLE ... LOGIN PASSWORD works on Neon.

-- 1) Roles -------------------------------------------------------------
CREATE ROLE windmill_runtime LOGIN PASSWORD :'windmill_password';
CREATE ROLE content_runtime LOGIN PASSWORD :'content_password';
CREATE ROLE content_migrator LOGIN PASSWORD :'content_password';

-- 2) Windmill database --------------------------------------------------
CREATE DATABASE windmill OWNER windmill_runtime;

-- 3) Business database --------------------------------------------------
CREATE DATABASE content_os OWNER content_migrator;

-- Windmill schema requirements: the official helm chart creates a dedicated
-- non-superuser role + schema; on managed PG the docs require:
--   CREATE SCHEMA IF NOT EXISTS windmill AUTHORIZATION windmill_runtime;
-- plus the pgcrypto + pg_sleep-related functions availability is standard.
-- Neon supports CREATE EXTENSION pgcrypto.
