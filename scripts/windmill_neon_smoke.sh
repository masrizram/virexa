#!/usr/bin/env bash
# Windmill-on-Neon smoke: create script then IMMEDIATELY run by hash path (server
# processes the create async via notify; run-by-hash avoids the name resolution race).
set -e
WM="${WM:-http://localhost:8003}"
NAME="smoke_$(date +%s)"

TOKEN=$(curl -s -X POST "$WM/api/auth/login" -H 'Content-Type: application/json' \
  -d '{"email":"admin@windmill.dev","password":"changeme"}')
echo "1. login ok"

HASH=$(curl -s -X POST "$WM/api/w/admins/scripts/create" \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d "{\"path\":\"u/admin/$NAME\",\"summary\":\"neon smoke\",\"language\":\"deno\",\"content\":\"export async function main(){ return {ok: true, db: 'neon-verified', ts: Date.now()} }\",\"description\":\"smoke\"}")
echo "2. hash=$HASH"

sleep 2
RUN=$(curl -s -m 120 -X POST "$WM/api/w/admins/jobs/run/h/$HASH" \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -d '{}')
echo "3. run=${RUN:0:150}"
# Response is the raw job UUID (not JSON)
JOB_ID=""
if echo "$RUN" | grep -qE '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'; then
  JOB_ID="$RUN"
else
  JOB_ID=$(echo "$RUN" | python3 -c 'import sys,json;print(json.load(sys.stdin).get("id",""))' 2>/dev/null || true)
fi
[ -n "$JOB_ID" ] || { echo "NO JOB ID"; exit 1; }

for i in $(seq 1 40); do
  sleep 1.5
  J=$(curl -s -m 30 "$WM/api/w/admins/jobs_u/get/$JOB_ID" -H "Authorization: Bearer $TOKEN")
  TYPE=$(echo "$J" | python3 -c 'import sys,json;print(json.load(sys.stdin).get("type",""))' 2>/dev/null || true)
  if [ "$TYPE" = "CompletedJob" ] || [ "$TYPE" = "Completed" ]; then
    echo "4. COMPLETED job=$JOB_ID"
    echo "5. RESULT: $(echo "$J" | python3 -c 'import sys,json;print(json.load(sys.stdin).get("result"))')"
    exit 0
  fi
  [ "$TYPE" = "FailedJob" ] && { echo "FAILED: ${J:0:300}"; exit 1; }
done
echo "TIMEOUT"; exit 1
