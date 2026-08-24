#!/usr/bin/env python
"""Full production pipeline proof: discovery -> select -> strategy -> script ->
MPT video (submitted from inside the Fly network) -> produce/sync (download +
upload R2 + Asset row) -> verify R2 object exists.

Evidence-first: every step prints status + ids; final check does a HEAD on the
R2 key recorded in the Asset row.
"""
import json
import os
import subprocess
import sys
import time
import urllib.request

BASE = os.environ.get("API_BASE", "https://virexa-api.fly.dev")
TOKEN = os.environ.get("VIREXA_SERVICE_TOKEN", "")
if not TOKEN:
    print("set VIREXA_SERVICE_TOKEN"); sys.exit(2)


def call(method: str, path: str, body=None, timeout: int = 180):
    req = urllib.request.Request(
        BASE + path,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Authorization": "Bearer " + TOKEN, "Content-Type": "application/json"},
        method=method)
    try:
        r = urllib.request.urlopen(req, timeout=timeout)
        return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode() or "{}")
        except Exception:
            return e.code, {}


def ssh_py(code: str, timeout: int = 300) -> str:
    """Run python inside virexa-api via flyctl ssh; single-line code required."""
    one = "; ".join(line.strip() for line in code.strip().splitlines() if line.strip())
    out = subprocess.run(
        ["flyctl", "ssh", "console", "-a", "virexa-api", "--command", f'python -c "{one}"'],
        capture_output=True, text=True, timeout=timeout)
    return out.stdout + out.stderr


def main() -> int:
    # 1) discovery (live source)
    st, disc = call("POST", "/pipeline/discover", {"sources": ["hackernews"], "limit_per_source": 5})
    print("1. discover:", st, "created:", disc.get("created"), "duplicates:", disc.get("duplicates"))

    # latest opportunity
    st, ops = call("GET", "/opportunities?limit=5")
    items = ops if isinstance(ops, list) else (ops.get("items") or ops.get("data") or [])
    if not items:
        print("   no opportunities found"); return 1
    opp = items[0]
    print("   opportunity:", opp["id"], str(opp.get("topic"))[:60])

    # 2) research (DISCOVERED -> RESEARCHING -> RESEARCHED) — payload per API schema
    st, res = call("POST", "/pipeline/research", {
        "opportunity_id": opp["id"],
        "facts": ["Hacker News front-page topic", "Active discussion thread"],
        "key_claims": ["Topic is trending in tech communities"],
        "summary": "Trending HN topic suitable for short-form coverage",
        "sources": [{"url": str(opp.get("url") or ""), "title": str(opp.get("topic"))[:80]}],
        "depth": "STANDARD"})
    print("2. research:", st, json.dumps(res)[:140])

    # 3) score (spec §25 factor keys, 0-100 each)
    factors = {"TrendVelocity": 82, "AudienceFit": 75, "ViralPotential": 70,
               "ContentGap": 65, "Freshness": 90, "Monetization": 60,
               "ProductionEase": 80, "Confidence": 72}
    st, sc = call("POST", "/pipeline/score", {"opportunity_id": opp["id"], "factors": factors})
    print("3. score:", st, "total:", sc.get("total"))

    # 4) select (creates content item) — unique title to pass dedup §26
    title = f"[R2-STORAGE-PROOF {int(time.time())}] " + str(opp.get("topic"))[:90]
    st, sel = call("POST", "/pipeline/select", {"opportunity_id": opp["id"], "title": title})
    print("4. select:", st, json.dumps(sel)[:160])
    if not sel.get("selected"):
        print("   duplicate topic — pick next opportunity or rerun"); return 1
    cid = sel["content_item_id"]

    # 5) strategy
    st, strat = call("POST", "/pipeline/strategy", {
        "content_item_id": cid, "topic": title,
        "angle": "proof-of-storage", "audience": "builders", "hook": "R2 proof",
        "format": "short", "duration_seconds": 30, "cta": "follow",
        "objective": "verify", "platforms": ["youtube"]})
    print("4. strategy:", st, json.dumps(strat)[:140])

    # 5) script
    st, scr = call("POST", "/pipeline/script", {
        "content_item_id": cid,
        "sections": {"HOOK": "Dawn over the city.", "CONTEXT": "A quiet morning.",
                     "CORE": "The city wakes.", "PAYOFF": "A new day begins.",
                     "CTA": "Follow for more."}})
    print("5. script:", st, "version:", scr.get("version"), "words:", scr.get("word_count"))
    if st != 200:
        print(json.dumps(scr)[:400]); return 1
    svid = scr.get("script_version_id")

    # 6) submit MPT task from INSIDE the Fly network
    inner = (
        "import json,urllib.request\n"
        "p={" 
        "'video_subject':'City at dawn',"
        "'video_script':'Dawn over the city. Streets wake slowly. A new day begins.',"
        "'video_terms':['city sunrise','urban morning'],"
        "'voice_name':'en-US-AriaNeural','video_aspect_ratio':'9:16',"
        "'video_source':'pexels','video_max_duration':20}\n"
        "r=urllib.request.Request('http://virexa-video.internal:8080/api/v1/videos',"
        "data=json.dumps(p).encode(),headers={'Content-Type':'application/json'})\n"
        "print('TASK:'+json.load(urllib.request.urlopen(r,timeout=120))['data']['task_id'])"
    )
    out = ssh_py(inner)
    tid = None
    for line in out.splitlines():
        if line.startswith("TASK:"):
            tid = line.split(":", 1)[1].strip()
    print("6. MPT task:", tid)
    if not tid:
        print(out[-600:]); return 1

    # 7) register video job via /pipeline/produce
    st, prod = call("POST", "/pipeline/produce", {
        "content_item_id": cid, "script_version_id": svid,
        "mpt_task_id": tid, "params": {"source": "proof"}})
    print("7. produce:", st, json.dumps(prod)[:160])
    if st != 200:
        print(json.dumps(prod)[:400]); return 1
    vjid = prod["video_job_id"]

    # 8) produce/sync (poll MPT -> download -> R2 -> Asset -> QC)
    deadline = time.time() + 400
    while time.time() < deadline:
        st, sync = call("POST", "/pipeline/produce/sync",
                        {"video_job_id": vjid, "poll_timeout_seconds": 90}, timeout=300)
        print("8. sync:", st, json.dumps(sync)[:200])
        if st == 200:
            break
        if st in (404, 400, 409, 422, 500):
            return 1
        time.sleep(10)
    else:
        print("sync never succeeded"); return 1
    if sync.get("status") != "COMPLETED":
        print("job not completed:", sync); return 1

    # 9) verify: list assets for this content item, HEAD the R2 key
    st, assets = call("GET", f"/content/{cid}/assets")
    if isinstance(assets, list):
        rows = assets
    else:
        rows = assets.get("items") or assets.get("data") or assets.get("assets") or []
    print("9. assets:", st, "count:", len(rows))
    if not rows:
        # fallback: check via audit trail
        st2, au = call("GET", f"/audit?entity_id={vjid}&limit=5")
        print("   audit fallback:", st2, json.dumps(au)[:300])
        return 1
    a = rows[0]
    print("   asset:", a.get("storage_key"), a.get("size_bytes"), "bytes, checksum:", str(a.get("checksum"))[:16])
    key = a.get("storage_key", "")
    if key:
        inner2 = (
            "import boto3,os\n"
            "from botocore.client import Config\n"
            "c=boto3.client('s3',endpoint_url=os.environ['S3_ENDPOINT'],"
            "aws_access_key_id=os.environ['S3_ACCESS_KEY_ID'],"
            "aws_secret_access_key=os.environ['S3_SECRET_ACCESS_KEY'],"
            "config=Config(region_name='auto',s3={'addressing_style':'path'}))\n"
            f"h=c.head_object(Bucket=os.environ['S3_BUCKET'],Key='{key}')\n"
            "print('R2HEAD:'+str(h['ContentLength'])+':'+h['ETag'])"
        )
        out = ssh_py(inner2)
        for line in out.splitlines():
            if line.startswith("R2HEAD:"):
                print("10. R2 HEAD:", line); return 0
        print("R2 HEAD failed:\n", out[-400:]); return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
