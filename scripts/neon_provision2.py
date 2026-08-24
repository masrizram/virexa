#!/usr/bin/env python
"""Neon provisioning step 2: roles + databases + grants, using owner password from
the create-project response (stored in .secrets/neon_project.json)."""
import json
import os
import subprocess

PROJECT = "red-rice-63329933"
HOST = "ep-soft-brook-azlt9k72.c-3.ap-southeast-1.aws.neon.tech"
BRANCH = "br-weathered-smoke-aza293wl"

d = json.load(open("C:/laraenv/www/virexa/.secrets/neon_project.json"))
OWNER_PW = d["connection_uris"][0]["connection_parameters"]["password"]

roles = {
    "windmill_runtime": f"wm-{PROJECT}",
    "content_runtime": f"cr-{PROJECT}",
    "content_migrator": f"cm-{PROJECT}",
}
out = {"project": PROJECT, "host": HOST, "roles": roles}

def psql(user, pw, db, sql):
    url = f"postgresql://{user}:{pw}@{HOST}/{db}?sslmode=require"
    r = subprocess.run(
        ["wsl", "docker", "exec", "-i", "virexa-pg", "psql", url, "-v", "ON_ERROR_STOP=0", "-c", sql],
        capture_output=True, text=True)
    return r.returncode, (r.stdout + r.stderr)[-400:]

# 1) roles (idempotent-ish: drop error text if exists)
sql_roles = ";".join(
    f"CREATE ROLE {n} LOGIN PASSWORD '{p}'" for n, p in roles.items()
)
code, txt = psql("neondb_owner", OWNER_PW, "neondb", sql_roles)
print("[roles]", code, txt[-200:])

# 2) databases: Neon requires DB creation via SQL on the endpoint owner connection? Try SQL first.
code, txt = psql("neondb_owner", OWNER_PW, "neondb",
                 f"CREATE DATABASE windmill OWNER windmill_runtime; CREATE DATABASE content_os OWNER content_migrator;")
print("[databases]", code, txt[-300:])

# 3) grants in content_os (connect as migrator — the owner)
grants = """
GRANT ALL ON SCHEMA public TO content_migrator;
GRANT USAGE ON SCHEMA public TO content_runtime;
ALTER DEFAULT PRIVILEGES FOR ROLE content_migrator IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO content_runtime;
ALTER DEFAULT PRIVILEGES FOR ROLE content_migrator IN SCHEMA public
  GRANT USAGE ON TYPES TO content_runtime;
"""
code, txt = psql("content_migrator", roles["content_migrator"], "content_os", grants)
print("[grants]", code, txt[-300:])

json.dump(out, open("C:/laraenv/www/virexa/.secrets/neon_roles.json", "w"), indent=1)
print("saved .secrets/neon_roles.json")
