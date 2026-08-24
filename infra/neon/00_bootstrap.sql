-- Neon bootstrap for Virexa (run as neondb_owner on the project endpoint, direct connection).
-- Verified 2026-08-24 on project red-rice-63329933 (aws-ap-southeast-1, PG16).
--
-- IMPORTANT (verified runtime evidence): Windmill's SQL migrations reference
-- roles windmill_admin / windmill_user / windmill_password. On Neon these must
-- exist cluster-wide and be granted to the runtime role, else Windmill fails
-- migration 20221211192539 with "role does not exist".

-- 1) Login roles (least privilege) ------------------------------------
CREATE ROLE windmill_runtime LOGIN PASSWORD '<WINDMILL_PW>';
CREATE ROLE content_migrator LOGIN PASSWORD '<CONTENT_PW>';
CREATE ROLE content_runtime LOGIN PASSWORD '<CONTENT_PW>';

-- 2) Windmill's expected group roles (NOLOGIN) ------------------------
CREATE ROLE windmill_admin NOLOGIN;
CREATE ROLE windmill_user NOLOGIN;
CREATE ROLE windmill_password NOLOGIN;

-- 3) Membership so windmill_runtime satisfies Windmill migrations ------
GRANT windmill_admin    TO windmill_runtime;
GRANT windmill_user     TO windmill_runtime;
GRANT windmill_password TO windmill_runtime;

-- 4) Databases: create via Neon API (owner is enforced there), e.g.:
--   POST /api/v2/projects/<id>/branches/<branch>/databases
--     {"database":{"name":"windmill","owner_name":"windmill_runtime"}}
--     {"database":{"name":"content_os","owner_name":"content_migrator"}}
-- (CREATE DATABASE over SQL fails on Neon with "must be able to SET ROLE".)

-- 5) Business DB grants (connect to content_os as content_migrator) ---
GRANT USAGE ON SCHEMA public TO content_runtime;
ALTER DEFAULT PRIVILEGES FOR ROLE content_migrator IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO content_runtime;
ALTER DEFAULT PRIVILEGES FOR ROLE content_migrator IN SCHEMA public
  GRANT USAGE ON TYPES TO content_runtime;
