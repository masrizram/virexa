#!/usr/bin/env python
"""Sync Virexa flows to Windmill (Fly instance).

Creates/updates scripts under workspace `virexa` paths:
  f/content/daily_cycle, f/content/discovery_daily, f/content/research_candidates,
  f/engagement/collect, f/system/health, f/system/daily_report
Plus a variable for the API base + service token.

Usage:
  python scripts/windmill_sync_flows.py [--token WM_TOKEN]

Env: WM_URL (default https://virexa-windmill.fly.dev)
     VIREXA_API_BASE (default https://virexa-api.fly.dev)
     VIREXA_SERVICE_TOKEN (required — set as Windmill variable)
"""
import json
import os
import sys
import urllib.request

WM = os.environ.get("WM_URL", "https://virexa-windmill.fly.dev")
API_BASE = os.environ.get("VIREXA_API_BASE", "https://virexa-api.fly.dev")

FLOWS = [
    ("f/content/daily_cycle", "flows/content/daily_cycle.ts"),
    ("f/content/discovery_daily", "flows/content/discovery_daily.ts"),
    ("f/content/research_candidates", "flows/content/research_candidates.ts"),
    ("f/engagement/collect", "flows/engagement/collect.ts"),
    ("f/system/health", "flows/system/health.ts"),
    ("f/system/daily_report", "flows/system/daily_report.ts"),
]

# lib/api.ts is inlined as a shared script f/lib/api (deno bundle)
LIB = ("f/lib/api", "flows/lib/api.ts")


def api(method: str, path: str, token: str, body: dict | None = None) -> dict:
    req = urllib.request.Request(
        f"{WM}{path}",
        method=method,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        data=json.dumps(body).encode() if body is not None else None,
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            raw = r.read().decode()
            try:
                return json.loads(raw) if raw else {}
            except json.JSONDecodeError:
                # create returns the raw script hash, not JSON
                return {"raw": raw}
    except urllib.error.HTTPError as e:
        detail = e.read().decode()[:400]
        raise SystemExit(f"HTTP {e.code} {path}: {detail}")


def create_or_update_script(token: str, path: str, content: str, summary: str) -> None:
    # Try create first; if exists (409/400), update via PUT
    body = {
        "path": path,
        "summary": summary,
        "language": "deno",
        "content": content,
        "description": "",
        "kind": "script",
        "schema": None,
        "is_template": False,
        "editor_version": None,
    }
    try:
        api("POST", "/api/w/virexa/scripts/create", token, body)
        print(f"  created {path}")
    except SystemExit as e:
        msg = str(e)
        if "409" in msg or "exists" in msg.lower() or "already" in msg.lower() or "conflict" in msg.lower():
            # update: needs parent_hash of the current version, path without p/ prefix
            cur = api("GET", f"/api/w/virexa/scripts/get/p/{path}", token)
            body["parent_hash"] = cur.get("hash")
            api("POST", f"/api/w/virexa/scripts/update/{path}", token, body)
            print(f"  updated {path}")
        else:
            raise


def main() -> None:
    token = None
    if "--token" in sys.argv:
        token = sys.argv[sys.argv.index("--token") + 1]
    if not token:
        token = os.environ.get("WM_TOKEN")
    if not token:
        raise SystemExit("No Windmill token (WM_TOKEN env or --token)")

    svc_token = os.environ.get("VIREXA_SERVICE_TOKEN")
    if not svc_token:
        raise SystemExit("VIREXA_SERVICE_TOKEN env required (to store as Windmill variable)")

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    print("1. lib script f/lib/api")
    with open(os.path.join(root, LIB[1])) as f:
        lib_src = f.read()
    # lib/api.ts imports nothing; in Windmill each flow imports from f/lib/api —
    # but Windmill deno scripts can import via https://esm.sh or internal bundles.
    # Simplest robust pattern: each flow inlines the api helper. We therefore
    # upload lib as a script that exports helpers via `export` (usable with
    # `import * from 'https://windmill.../f/lib/api'`)? Not reliable.
    # → The sync inlines the helper into each flow at upload time instead.
    helper = lib_src
    # strip imports (helpers are inlined) and the module docstring header
    for imp in (
        'import { post } from "../../lib/api";',
        'import { get, post } from "../../lib/api";',
        'import { get } from "../lib/api";',
        'import { post } from "../lib/api";',
    ):
        helper = helper.replace(imp, "")
    # drop the leading /** ... */ docblock so only executable code remains
    if helper.lstrip().startswith("/**"):
        helper = helper.split("*/", 1)[1]

    for path, rel in FLOWS:
        with open(os.path.join(root, rel)) as f:
            src = f.read()
        src = src.replace('import { post } from "../../lib/api";', "")
        src = src.replace('import { get, post } from "../../lib/api";', "")
        src = src.replace('import { get } from "../lib/api";', "")
        src = src.replace('import { post } from "../lib/api";', "")
        # inject helper before `export async function main`
        marker = "export async function main"
        src = src.replace(marker, helper + "\n" + marker, 1)
        summary = rel.replace("flows/", "").replace(".ts", "")
        create_or_update_script(token, path, src, summary)

    print("2. variables")
    # variables: u/virexa/virexa_api_base (string, non-secret) + service token (secret)
    vars_to_set = [
        {
            "path": "u/virexa/virexa_api_base",
            "value": API_BASE,
            "is_secret": False,
            "description": "Virexa API base URL used by flows",
        },
        {
            "path": "u/virexa/virexa_service_token",
            "value": svc_token,
            "is_secret": True,
            "description": "Service token for the Virexa API",
        },
    ]
    for v in vars_to_set:
        try:
            api("POST", "/api/w/virexa/variables/create", token, v)
            print(f"  created var {v['path']}")
        except SystemExit as e:
            if "409" in str(e) or "exists" in str(e).lower() or "already" in str(e).lower() or "conflict" in str(e).lower():
                api("POST", f"/api/w/virexa/variables/update/{v['path']}", token, v)
                print(f"  updated var {v['path']}")
            else:
                raise

    print("3. schedules")
    # schedules via API: f/content/discovery_daily daily 06:00 UTC, f/system/health hourly
    schedules = [
        {
            "path": "f/content/discovery_daily",
            "schedule": "0 0 6 * * *",
            "timezone": "Asia/Jakarta",
            "enabled": True,
            "script_path": "f/content/discovery_daily",
            "args": {},
        },
        {
            "path": "f/system/health",
            "schedule": "0 0 * * * *",
            "timezone": "Asia/Jakarta",
            "enabled": True,
            "script_path": "f/system/health",
            "args": {},
        },
    ]
    for s in schedules:
        body = {
            "path": s["path"],
            "schedule": s["schedule"],
            "timezone": s["timezone"],
            "enabled": s["enabled"],
            "script_path": s["script_path"],
            "is_flow": False,
            "args": s["args"],
        }
        try:
            api("POST", "/api/w/virexa/schedules/create", token, body)
            print(f"  created schedule {s['path']} ({s['schedule']})")
        except SystemExit as e:
            if "409" in str(e) or "exists" in str(e).lower() or "already" in str(e).lower():
                print(f"  schedule exists {s['path']}")
            else:
                raise

    print("DONE")


if __name__ == "__main__":
    main()
