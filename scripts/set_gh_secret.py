#!/usr/bin/env python
"""Set FLY_CI_DEPLOY_TOKEN as a GitHub Actions secret on masrizram/virexa.
Uses repo-scope GitHub token from git credential helper; encrypts with PyNaCl
via libsodium sealed box (GitHub API requirement).
Requires: pip install pynacl (once).
"""
import base64
import json
import os
import subprocess
import sys
import urllib.request

REPO = "masrizram/virexa"

# 1. GitHub token from credential helper
cred = subprocess.run(["git", "credential", "fill"], input="protocol=https\nhost=github.com\n\n",
                      capture_output=True, text=True).stdout
gh_token = [l.split("=", 1)[1] for l in cred.splitlines() if l.startswith("password=")][0]

# 2. Fly deploy token from env
fly_token = os.environ["FLY_TOKEN"]

# 3. Get repo public key
req = urllib.request.Request(f"https://api.github.com/repos/{REPO}/actions/secrets/public-key",
                             headers={"Authorization": f"Bearer {gh_token}", "Accept": "application/vnd.github+json"})
pk = json.load(urllib.request.urlopen(req))

# 4. Encrypt (libsodium sealed box)
from nacl import encoding, public

key = public.PublicKey(pk["key"].encode(), encoding.Base64Encoder())
sealed = public.SealedBox(key).encrypt(fly_token.encode())
b64 = base64.b64encode(sealed).decode()

# 5. PUT secret
req = urllib.request.Request(
    f"https://api.github.com/repos/{REPO}/actions/secrets/FLY_CI_DEPLOY_TOKEN",
    data=json.dumps({"encrypted_value": b64, "key_id": pk["key_id"]}).encode(),
    headers={"Authorization": f"Bearer {gh_token}", "Accept": "application/vnd.github+json"},
    method="PUT")
resp = urllib.request.urlopen(req)
print("secret set:", resp.status)
