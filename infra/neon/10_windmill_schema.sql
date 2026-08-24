-- Run connected to the windmill database as its owner (or windmill_runtime).
-- Mirrors Windmill's official managed-Postgres setup (helm chart values):
-- a dedicated schema owned by the runtime role, required extensions.

CREATE SCHEMA IF NOT EXISTS windmill AUTHORIZATION windmill_runtime;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Windmill's dedicated role must be able to create/alter its own tables:
GRANT ALL ON SCHEMA windmill TO windmill_runtime;
ALTER ROLE windmill_runtime IN DATABASE windmill SET search_path = windmill, public;

-- (Windmill >= 1.367 expects role `windmill_user`? No: it uses DATABASE_URL's user.)
-- The server and workers all connect with DATABASE_URL=postgresql://windmill_runtime:...@host/windmill?sslmode=require
-- Set the schema via env: DATABASE_URL includes options=-csearch_path%3Dwindmill
