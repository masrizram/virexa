#!/usr/bin/env python
"""YouTube OAuth helper — installed-app loopback flow (spec §35 official OAuth).

Google shut down the OOB flow (urn:ietf:wg:oauth:2.0:oob) in 2022; this uses
the supported loopback redirect: a local HTTP server catches Google's redirect
and the code is exchanged automatically. Operator runs locally; secrets never
leave this machine except to Fly.

One-shot usage (env: YOUTUBE_CLIENT_ID, YOUTUBE_CLIENT_SECRET):
  python scripts/youtube_oauth.py consent
    -> opens the browser; you approve with the REAL YouTube account;
       script catches the redirect, exchanges the code, verifies the channel,
       prints the refresh token + account handle.

Manual fallback (e.g. browser on another machine):
  python scripts/youtube_oauth.py url          # print consent URL only
  python scripts/youtube_oauth.py exchange <CODE>  # code from the redirect URL

Store the result (Fly):
  flyctl secrets set -a virexa-api \
    YOUTUBE_CLIENT_ID=... YOUTUBE_CLIENT_SECRET=... YOUTUBE_REFRESH_TOKEN=...

Prerequisites on the Google Cloud project (project "virexa"):
  1. YouTube Data API v3 ENABLED (APIs & Services -> Library)
  2. OAuth consent screen: External, status Testing, scopes youtube.upload +
     youtube.readonly + youtube.force-ssl added, and rizkiiramdaniii@gmail.com
     added as TEST USER (otherwise consent returns access_denied)
  3. OAuth client of type "Desktop app" (loopback ports work out of the box)
"""
from __future__ import annotations

import http.server
import json
import os
import socketserver
import sys
import threading
import urllib.parse
import urllib.request
import webbrowser

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
    "https://www.googleapis.com/auth/youtube.force-ssl",
]
PORT = 8788
REDIRECT_URI = f"http://localhost:{PORT}"


def creds() -> tuple[str, str]:
    cid = os.environ.get("YOUTUBE_CLIENT_ID", "")
    sec = os.environ.get("YOUTUBE_CLIENT_SECRET", "")
    if not cid or not sec:
        print("export YOUTUBE_CLIENT_ID and YOUTUBE_CLIENT_SECRET first")
        sys.exit(2)
    return cid, sec


def consent_url() -> str:
    cid, _ = creds()
    q = urllib.parse.urlencode({
        "client_id": cid,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": " ".join(SCOPES),
        "access_type": "offline",  # we need a refresh token
        "prompt": "consent",       # force refresh_token issuance
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
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            tok = json.loads(r.read().decode())
    except urllib.error.HTTPError as exc:
        body = exc.read().decode()[:500]
        print(f"token exchange failed: HTTP {exc.code} {body}")
        sys.exit(1)
    if "refresh_token" not in tok:
        print("WARNING: no refresh_token in response (Google skips re-issue if "
              "the account already consented). Retry with prompt=consent.")
        sys.exit(1)
    return tok


def whoami(access_token: str) -> dict:
    url = "https://www.googleapis.com/youtube/v3/channels?part=snippet&mine=true"
    req = urllib.request.Request(url, headers={"Authorization": "Bearer " + access_token})
    with urllib.request.urlopen(req, timeout=30) as r:
        d = json.loads(r.read().decode())
    items = d.get("items") or []
    if not items:
        return {"error": "no channel on this account (a channel is required to upload)"}
    s = items[0]["snippet"]
    return {"channel_id": items[0]["id"], "title": s.get("title", ""),
            "handle": s.get("customUrl", "")}


class _Catcher(http.server.BaseHTTPRequestHandler):
    code: str = ""
    error: str = ""

    def do_GET(self):  # noqa: N802 — http.server API
        q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        if "code" in q:
            _Catcher.code = q["code"][0]
            self.send_response(200)
            body = "<h2>OK — kembali ke terminal. Tab ini bisa ditutup.</h2>".encode()
        else:
            _Catcher.error = q.get("error", ["unknown"])[0]
            self.send_response(400)
            body = f"<h2>Gagal: {_Catcher.error}</h2>".encode()
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_args):  # silence request logging
        pass


def run_consent() -> int:
    url = consent_url()
    print("Consent URL:", url)
    print(f"Waiting for Google's redirect on http://localhost:{PORT} "
          "(approve in the browser; timeout 5 minutes)...")

    server = socketserver.TCPServer(("127.0.0.1", PORT), _Catcher)
    server.timeout = 300
    threading.Thread(target=server.handle_request, daemon=True).start()

    webbrowser.open(url)

    deadline = threading.Event()
    import time
    start = time.time()
    while time.time() - start < 300:
        if _Catcher.code or _Catcher.error:
            break
        time.sleep(0.5)
    server.server_close()

    if _Catcher.error:
        print("Consent error:", _Catcher.error,
              "(access_denied usually = email not added as TEST USER on the "
              "consent screen, or YouTube Data API v3 not enabled)")
        return 1
    if not _Catcher.code:
        print("Timed out waiting for the redirect.")
        return 1

    tok = exchange(_Catcher.code)
    info = whoami(tok["access_token"])
    print()
    print("REFRESH_TOKEN:", tok["refresh_token"])
    print("ACCOUNT:", json.dumps(info, ensure_ascii=False))
    print()
    print("Next:")
    print("  flyctl secrets set -a virexa-api \\")
    print("    YOUTUBE_CLIENT_ID=$YOUTUBE_CLIENT_ID \\")
    print("    YOUTUBE_CLIENT_SECRET=$YOUTUBE_CLIENT_SECRET \\")
    print(f"    YOUTUBE_REFRESH_TOKEN={tok['refresh_token']}")
    return 0


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 2
    cmd = argv[1]
    if cmd == "consent":
        return run_consent()
    if cmd == "url":
        print(consent_url())
        return 0
    if cmd == "exchange":
        if len(argv) < 3:
            print("usage: youtube_oauth.py exchange <CODE>")
            return 2
        tok = exchange(argv[2])
        print("REFRESH_TOKEN:", tok["refresh_token"])
        print("ACCOUNT:", json.dumps(whoami(tok["access_token"]), ensure_ascii=False))
        return 0
    print("unknown command:", cmd)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
