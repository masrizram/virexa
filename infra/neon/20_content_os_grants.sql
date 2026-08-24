-- Run connected to content_os as content_migrator (Alembic runs as this role).
-- Least privilege: migrator owns app schema; runtime gets DML only.

GRANT ALL ON SCHEMA public TO content_migrator;

-- Runtime: usage on schema + DML on all current and future tables/sequences.
GRANT USAGE ON SCHEMA public TO content_runtime;
ALTER DEFAULT PRIVILEGES FOR ROLE content_migrator IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO content_runtime;
ALTER DEFAULT PRIVILEGES FOR ROLE content_migrator IN SCHEMA public
  GRANT USAGE, SELECT ON SEQUENCES TO content_runtime;

-- Optional analytics read-only role:
CREATE ROLE analytics_reader LOGIN PASSWORD :'analytics_password';
GRANT USAGE ON SCHEMA public TO analytics_reader;
ALTER DEFAULT PRIVILEGES FOR ROLE content_migrator IN SCHEMA public
  GRANT SELECT ON TABLES TO analytics_reader;
