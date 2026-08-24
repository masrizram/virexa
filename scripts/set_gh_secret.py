#!/usr/bin/env python
"""Delete then re-set all 5 Fly deploy tokens as GitHub secrets, then trigger deploy workflow.
Verifies each token by calling Fly API before setting."""
import base64
import json
import os
import subprocess
import urllib.request

REPO = "masrizram/virexa"
APPS = ["virexa-api", "virexa-web", "virexa-windmill", "virexa-windmill-worker", "virexa-video"]

gh_token = os.environ["GH_TOKEN"]

from nacl import encoding, public

def gh_api(url, data=None, method="GET"):
    req = urllib.request.Request(url, data=json.dumps(data).encode() if data else None,
        headers={"Authorization": f"Bearer {gh_token}", "Accept": "application/vnd.github+json"},
        method=method)
    return urllib.request.urlopen(req)

pk = json.load(gh_api(f"https://api.github.com/repos/{REPO}/actions/secrets/public-key"))
key = public.PublicKey(pk["key"].encode(), encoding.Base64Encoder())
box = public.SealedBox(key)

for app in APPS:
    name = f"FLY_TOKEN_{app.upper().replace('-', '_')}"
    # delete first (404 ok if missing)
    try:
        gh_api(f"https://api.github.com/repos/{REPO}/actions/secrets/{name}", method="DELETE")
    except Exception:
        pass
    # create + validate token
    out = subprocess.run(["flyctl", "tokens", "create", "deploy", "-a", app],
                         capture_output=True, text=True)
    token = out.stdout.strip()
    ok = token.startswith("FlyV1 ")
    if ok:
        # validate against Fly API (proper GraphQL payload)
        try:
            req = urllib.request.Request("https://api.fly.io/graphql",
                data=json.dumps({"query": "query{app(name:\"" + app + "\"){name}}"}).encode(),
                headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"})
            d = json.load(urllib.request.urlopen(req, timeout=20))
            ok = d.get("data", {}).get("app", {}).get("name") == app
            if not ok:
                print(f"{app}: Fly API returned: {str(d)[:150]}")
        except Exception as e:
            print(f"{app}: Fly API validation FAILED: {str(e)[:100]}")
            ok = False
    if not ok:
        print(f"{app}: token create FAILED: {out.stderr[:150]}")
        continue
    sealed = box.encrypt(token.encode())
    b64 = base64.b64encode(sealed).decode()
    resp = gh_api(f"https://api.github.com/repos/{REPO}/actions/secrets/{name}",
                  data={"encrypted_value": b64, "key_id": pk["key_id"]}, method="PUT")
    print(f"{name}: {resp.status} (token {len(token)} chars, validated)")

# trigger deploy workflow
resp = gh_api(f"https://api.github.com/repos/{REPO}/actions/workflows/deploy.yml/dispatches",
              data={"ref": "main"}, method="POST")
print("workflow dispatch:", resp.status)
