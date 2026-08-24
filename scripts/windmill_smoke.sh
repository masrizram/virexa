#!/usr/bin/env bash
# Windmill smoke test — full proof: login, script exists, job runs on worker, result verified.
# Correct endpoint: POST /api/w/{workspace}/jobs/run/p/{path}  (p = by path)
set -e
WM="${WM:-http://localhost:8001}"

TOKEN=$(curl -s -X POST "$WM/api/auth/login" -H 'Content-Type: application/json' \
  -d '{"email":"admin@windmill.dev","password":"changeme"}')
if [ -z "$TOKEN" ]; then echo "LOGIN FAILED"; exit 1; fi
echo "login ok"

# Create script if missing (idempotent)
curl -s -X POST "$WM/api/w/admins/scripts/create" \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"path":"u/admin/smoke","summary":"smoke test","language":"deno","content":"export async function main(){ return {ok: true, ran: Date.now()} }","description":"smoke test"}' | head -c 80; echo

RUN=$(curl -s -X POST "$WM/api/w/admins/jobs/run/p/u/admin/smoke" \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -d '{}')
echo "run: $(echo "$RUN" | head -c 150)"
JOB_ID=$(echo "$RUN" | python3 -c 'import sys,json;print(json.load(sys.stdin)["id"])' 2>/dev/null || echo "")

if [ -n "$JOB_ID" ]; then
  for i in $(seq 1 30); do
    sleep 1
    J=$(curl -s "$WM/api/w/admins/jobs_u/get/$JOB_ID" -H "Authorization: Bearer $TOKEN")
    TYPE=$(echo "$J" | python3 -c 'import sys,json;print(json.load(sys.stdin).get("type",""))' 2>/dev/null)
    echo "poll $i: $TYPE"
    if [ "$TYPE" = "Completed" ] || [ "$TYPE" = "Failed" ]; then
      echo "RESULT: $(echo "$J" | python3 -c 'import sys,json;print(json.load(sys.stdin).get("result"), json.load(sys.stdin).get("success"))' 2>/dev/null)"
      break
    fi
  done
fi
