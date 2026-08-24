#!/usr/bin/env python
"""Check latest CI workflow run status + failed job steps (read-only)."""
import json
import os
import subprocess
import urllib.request

def api(url, token=None):
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, headers=headers)
    return json.load(urllib.request.urlopen(req, timeout=30))

# token from remote url (same pattern as set_gh_secret.py)
remote = subprocess.run(["git", "remote", "get-url", "origin"],
                        capture_output=True, text=True, cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))).stdout
token = ""
if "@" in remote:
    token = remote.split("https://masrizram:")[1].split("@")[0] if "https://masrizram:" in remote else ""

runs = api("https://api.github.com/repos/masrizram/virexa/actions/workflows/ci.yml/runs?per_page=1")["workflow_runs"]
run = runs[0]
print("ci run:", run["id"], run["head_sha"][:7], run["status"], run["conclusion"])
jobs = api(f"https://api.github.com/repos/masrizram/virexa/actions/runs/{run['id']}/jobs", token)
for j in jobs["jobs"]:
    print("job:", j["name"], "|", j["conclusion"])
    if j["conclusion"] == "failure":
        for s in j.get("steps", []):
            if s["conclusion"] != "success" and s["conclusion"] != "skipped":
                print("  step FAILED:", s["number"], s["name"])
