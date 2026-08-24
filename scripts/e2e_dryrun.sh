#!/usr/bin/env bash
# E2E dry-run against a Virexa API (local or Fly). Robust JSON via python.
# Env: API_BASE, optional VIREXA_SERVICE_TOKEN when API auth is enabled.
set -uo pipefail

API_BASE="${API_BASE:-http://localhost:8000}"
TOKEN="${VIREXA_SERVICE_TOKEN:-}"
PASS=0; FAIL=0; BRAND="e2e-$(date +%s)"

api() { # method path [json_body]
  local m="$1" p="$2" b="${3:-}"
  if [ -n "$TOKEN" ]; then
    if [ -n "$b" ]; then
      curl -sf -m 60 -X "$m" "$API_BASE$p" -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -d "$b"
    else
      curl -sf -m 60 -X "$m" "$API_BASE$p" -H "Authorization: Bearer $TOKEN"
    fi
  else
    if [ -n "$b" ]; then
      curl -sf -m 60 -X "$m" "$API_BASE$p" -H 'Content-Type: application/json' -d "$b"
    else
      curl -sf -m 60 -X "$m" "$API_BASE$p"
    fi
  fi
}

jqpy() { python3 -c "import sys,json; d=json.load(sys.stdin); print(d$1)" 2>/dev/null; }
step() { printf '\n== %s ==\n' "$1"; }
check() {
  if [ "$2" == "$3" ]; then echo "PASS: $1 ($3)"; PASS=$((PASS+1));
  else echo "FAIL: $1 expected=$2 got=$3"; FAIL=$((FAIL+1)); fi
}

step "1. Health"
H=$(api GET /healthz | jqpy "['status']"); check "healthz" "ok" "$H"

step "2. Safety toggle round-trip"
api POST /safety '{"state":"EMERGENCY_STOP"}' >/dev/null
S=$(api GET /safety | jqpy "['state']"); check "safety=EMERGENCY_STOP" "EMERGENCY_STOP" "$S"
api POST /safety '{"state":"RUNNING"}' >/dev/null
S=$(api GET /safety | jqpy "['state']"); check "safety=RUNNING" "RUNNING" "$S"

step "3. Discover"
D=$(api POST /pipeline/discover "{\"brand\":\"$BRAND\",\"sources\":[\"hackernews\"],\"limit_per_source\":5}")
CREATED=$(echo "$D" | jqpy "['created']"); echo "discovered: $CREATED (+$(echo "$D" | jqpy "['duplicates']") dup)"

step "4. Opportunities listed"
OPPS=$(api GET "/opportunities?limit=5")
FIRST=$(echo "$OPPS" | jqpy "[0]['topic']" 2>/dev/null)
echo "opportunities: $([ -n "$FIRST" ] && [ "$FIRST" != "None" ] && echo has || echo none)"

step "5. Score top opportunity"
OPP_ID=$(echo "$OPPS" | jqpy "[0]['id']")
if [ -n "$OPP_ID" ] && [ "$OPP_ID" != "None" ] && [ "$OPP_ID" != "" ]; then
  SC=$(api POST /pipeline/score "{\"opportunity_id\":\"$OPP_ID\",\"factors\":{\"TrendVelocity\":80,\"AudienceFit\":70,\"ViralPotential\":60,\"ContentGap\":75,\"Freshness\":90,\"Monetization\":50,\"ProductionEase\":85,\"Confidence\":80},\"penalties\":{\"RiskPenalty\":2,\"SaturationPenalty\":3}}")
  TOTAL=$(echo "$SC" | jqpy "['total']"); echo "score total: $TOTAL"
  check "score recorded" "True" "$([ -n "$TOTAL" ] && [ "$TOTAL" != "None" ] && echo True || echo False)"
else
  echo "SKIP: no opportunities (discovery source unreachable?)"
fi

step "Summary"
echo "PASS=$PASS FAIL=$FAIL"
[ "$FAIL" -eq 0 ]
