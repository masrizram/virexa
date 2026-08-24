#!/usr/bin/env python
"""Set multiple Fly deploy tokens as GitHub Actions secrets (one per app).
Env: GH_TOKEN (github token), FLY_API_TOKEN (flyctl token from operator machine)
"""
import base64
import json
import os
import subprocess
import urllib.request

REPO = "masrizram/virexa"
APPS = ["virexa-api", "virexa-web", "virexa-windmill", "virexa-windmill-worker", "virexa-video"]

gh_token = os.environ["GH_TOKEN"]
fly_operator_token = os.environ["FLY_API_TOKEN"]  # for creating tokens via flyctl locally

# Get repo public key
req = urllib.request.Request(f"https://api.github.com/repos/{REPO}/actions/secrets/public-key",
                             headers={"Authorization": f"Bearer {gh_token}", "Accept": "application/vnd.github+json"})
pk = json.load(urllib.request.urlopen(req))

from nacl import encoding, public
key = public.PublicKey(pk["key"].encode(), encoding.Base64Encoder())

def set_secret(name: str, value: str):
    sealed = public.SealedBox(key).encrypt(value.encode())
    b64 = base64.b64encode(sealed).decode()
    req = urllib.request.Request(
        f"https://api.github.com/repos/{REPO}/actions/secrets/{name}",
        data=json.dumps({"encrypted_value": b64, "key_id": pk["key_id"]}).encode(),
        headers={"Authorization": f"Bearer {gh_token}", "Accept": "application/vnd.github+json"},
        method="PUT")
    resp = urllib.request.urlopen(req)
    print(f"{name}: {resp.status}")

for app in APPS:
    out = subprocess.run(["flyctl", "tokens", "create", "deploy", "-a", app],
                         capture_output=True, text=True)
    token = out.stdout.strip()
    if token.startswith("FlyV1 ") or token.startswith("FlyV2 ") or len(token) < 100:
        set_secret(f"FLY_TOKEN_{app.upper().replace('-', '_')}", token)
    else:
        print(f"{app}: FAILED to create token: {out.stderr[:200]}")
