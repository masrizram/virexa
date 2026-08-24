#!/usr/bin/env python
"""End-to-end MPT video generation test through the Fly private network.

Working method (no SFTP quoting hell):
  1. write helper python to a local temp file
  2. upload via `flyctl ssh console` with stdin redirect
  3. submit + poll via `flyctl ssh console --command`

Usage:  python scripts/mpt_video_test.py [--voice en-US-AriaNeural]
Exit 0 on SUCCESS (state=1 + videos non-empty), 1 on failure/timeout.
"""
import argparse
import os
import subprocess
import sys
import tempfile
import time

HELPER = '''
import json, sys, urllib.request
BASE = "http://virexa-video.internal:8080"

def submit():
    payload = {
        "video_subject": "The quiet beauty of Jakarta at dawn",
        "video_script": ("Sunrise breaks over the Jakarta skyline, painting towers in soft gold. "
                         "Streets begin to stir as the city wakes. From the harbor to the towers, "
                         "a new day starts quietly, full of promise."),
        "video_terms": ["jakarta skyline", "city sunrise", "urban morning"],
        "voice_name": "__VOICE__",
        "video_aspect_ratio": "9:16",
        "video_concat_mode": "random",
        "video_clip_duration": 3,
        "video_count": 1,
        "video_source": "pexels",
        "video_max_duration": 30,
    }
    req = urllib.request.Request(BASE + "/api/v1/videos",
                                 data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"},
                                 method="POST")
    resp = json.load(urllib.request.urlopen(req, timeout=120))
    print("TASKID:" + resp["data"]["task_id"])

def poll(tid):
    resp = json.load(urllib.request.urlopen(BASE + "/api/v1/tasks/" + tid, timeout=60))
    d = resp["data"]
    print("STATE:" + str(d["state"]))
    print("PROGRESS:" + str(d.get("progress", "")))
    err = (d.get("error") or "")[:400]
    if err:
        print("ERR:" + err)
    for v in (d.get("videos") or []) + (d.get("combined_videos") or []):
        print("VIDEO:" + v)

{"submit": submit}.get(sys.argv[1], lambda: poll(sys.argv[2]))()
'''

REMOTE = "/tmp/mpt_probe.py"


def sh(cmd: str, stdin_file: str | None = None, timeout: int = 300) -> str:
    stdin = open(stdin_file, "rb") if stdin_file else subprocess.DEVNULL
    try:
        out = subprocess.run(cmd, shell=True, stdin=stdin,
                             capture_output=True, text=True, timeout=timeout)
        return out.stdout + out.stderr
    finally:
        if stdin_file:
            stdin.close()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--voice", default="en-US-AriaNeural")
    ap.add_argument("--polls", type=int, default=55, help="poll attempts (10s apart)")
    args = ap.parse_args()

    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False,
                                     encoding="utf-8") as f:
        f.write(HELPER.replace("__VOICE__", args.voice))
        local = f.name

    up = sh(f'flyctl ssh console -a virexa-api '
            f'--command "python -c \\"import sys; open(\'{REMOTE}\',\'w\').write(sys.stdin.read())\\""',
            stdin_file=local)
    os.unlink(local)
    print("helper uploaded:", "ok" if "Traceback" not in up else "FAILED")

    out = sh(f'flyctl ssh console -a virexa-api --command "python {REMOTE} submit"')
    tid = None
    for line in out.splitlines():
        if line.startswith("TASKID:"):
            tid = line.split(":", 1)[1].strip()
    if not tid:
        print("SUBMIT FAILED:\n", out[-800:])
        return 1
    print("task:", tid)

    for i in range(args.polls):
        time.sleep(10)
        out = sh(f'flyctl ssh console -a virexa-api --command "python {REMOTE} poll {tid}"')
        state = prog = err = ""
        vids = []
        for line in out.splitlines():
            if line.startswith("STATE:"):
                state = line.split(":", 1)[1]
            elif line.startswith("PROGRESS:"):
                prog = line.split(":", 1)[1]
            elif line.startswith("ERR:"):
                err = line.split(":", 1)[1]
            elif line.startswith("VIDEO:"):
                vids.append(line.split(":", 1)[1])
        print(f"[{(i+1)*10}s] state={state} progress={prog} videos={len(vids)}")
        if err:
            print("error:", err[:300])
        if state in ("-1", "1") or vids:
            if vids or state == "1":
                print("SUCCESS — videos:")
                for v in vids:
                    print("  ", v)
                return 0
            print("FAILED state:", state)
            return 1
    print("TIMEOUT")
    return 1


if __name__ == "__main__":
    sys.exit(main())
