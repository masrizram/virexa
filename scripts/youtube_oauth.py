#!/usr/bin/env python
"""YouTube OAuth helper — installed-app flow (spec §35 official OAuth, no browser automation).

Steps (operator runs locally, secrets never leave this machine except to Fly):

  1. Export the Google OAuth client you created in Google Cloud Console:
       export YOUTUBE_CLIENT_ID=...apps.googleusercontent.com
       export YOUTUBE_CLIENT_SECRET=...
  2. python scripts/youtube_oauth.py url
     -> prints the consent URL; open it in a browser, sign in with the REAL
        YouTube account, approve, copy the ?code=... from the redirect page.
  3. python scripts/youtube_oauth.py exchange <CODE>
     -> prints refresh_token + first access_token; verifies with a channels.list
        call so you know the account handle before anything is uploaded.
  4. Store (Fly):
       flyctl secrets set -a virexa-api \
         YOUTUBE_CLIENT_ID=... YOUTUBE_CLIENT_SECRET=... YOUTUBE_REFRESH_TOKEN=...
"""
from __future__ import annotations

import json
import os
import sys
import urllib.parse
import urllib.request

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
]
REDIRECT_URI = "urn:ietf:wg:oauth:2.0:oob"  # out-of-band: user pastes the code


def creds() -> tuple[str, str]:
    cid = os.environ.get("YOUTUBE_CLIENT_ID", "")
    sec = os.environ.get("YOUTUBE_CLIENT_SECRET", "")
    if not cid or not sec:
        print("export YOUTUBE_CLIENT_ID and YOUTUBE_CLIENT_SECRET first"); sys.exit(2)
    return cid, sec


def consent_url() -> str:
    cid, _ = creds()
    q = urllib.parse.urlencode({
        "client_id": cid,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": " ".join(SCOPES),
        "access_type": "offline",          # we need a refresh token
        "prompt": "consent",               # force refresh_token issuance
    })
    return f"{AUTH_URL}?{q}"


def exchange(code: str) -> dict:
    cid, sec = creds()
    data = urllib.parse.urlencode({
        "code": code, "client_id": cid, "client_secret": sec,
        "redirect_uri": REDIRECT_URI, "grant_type": "authorization_code",
    }).encode()
    req = urllib.request.Request(TOKEN_URL, data=data,
                                 headers={"Content-Type": "application/x-www-form-urlencoded"})
    with urllib.request.urlopen(req, timeout=30) as r:
        tok = json.loads(r.read().decode())
    if "refresh_token" not in tok:
        print("WARNING: no refresh_token in response (account already consented before "
              "and Google skips re-issue). Re-run the consent URL with prompt=consent."); sys.exit(1)
    return tok


def whoami(access_token: str) -> dict:
    url = ("https://www.googleapis.com/youtube/v3/channels?part=snippet&mine=true")
    req = urllib.request.Request(url, headers={"Authorization": "Bearer " + access_token})
    with urllib.request.urlopen(req, timeout=30) as r:
        d = json.loads(r.read().decode())
    items = d.get("items") or []
    if not items:
        return {"error": "no channel on this account (a channel is required to upload)"}
    s = items[0]["snippet"]
    return {"channel_id": items[0]["id"], "title": s.get("title", ""),
            "handle": s.get("customUrl", "")}


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__); return 2
    cmd = argv[1]
    if cmd == "url":
        print(consent_url())
        return 0
    if cmd == "exchange":
        if len(argv) < 3:
            print("usage: youtube_oauth.py exchange <CODE>"); return 2
        tok = exchange(argv[2])
        info = whoami(tok["access_token"])
        print("REFRESH_TOKEN:", tok["refresh_token"])
        print("ACCESS_TOKEN (short-lived):", tok["access_token"][:12] + "...")
        print("SCOPES:", tok.get("scope", ""))
        print("ACCOUNT:", json.dumps(info))
        print()
        print("Next:")
        print("  flyctl secrets set -a virexa-api YOUTUBE_CLIENT_ID=... "
              "YOUTUBE_CLIENT_SECRET=... YOUTUBE_REFRESH_TOKEN=" + tok["refresh_token"])
        return 0
    print("unknown command:", cmd); return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
