#!/usr/bin/env bash
# End-to-end dry-run verification against a running Virexa API (spec §64-65).
# Usage: API_BASE=http://localhost:8000 bash scripts/e2e_dryrun.sh
set -euo pipefail

API_BASE="${API_BASE:-http://localhost:8000}"
PASS=0; FAIL=0; BRAND="e2e-$(date +%s)"

step() { printf '\n== %s ==\n' "$1"; }
check() { # name, expected, actual
  if [ "$2" == "$3" ]; then echo "PASS: $1 ($3)"; PASS=$((PASS+1));
  else echo "FAIL: $1 expected=$2 got=$3"; FAIL=$((FAIL+1)); fi
}
jsonq() { PYTHONPATH= python -c "import sys,json; d=json.load(sys.stdin); print(d$1)" 2>/dev/null; }

step "1. Health"
H=$(curl -sf "$API_BASE/healthz" | jsonq "['status']"); check "healthz" "ok" "$H"

step "2. Safety toggle round-trip"
curl -sf -X POST "$API_BASE/safety" -H 'Content-Type: application/json' -d '{"state":"EMERGENCY_STOP"}' >/dev/null
S=$(curl -sf "$API_BASE/safety" | jsonq "['state']"); check "safety=EMERGENCY_STOP" "EMERGENCY_STOP" "$S"
curl -sf -X POST "$API_BASE/safety" -H 'Content-Type: application/json' -d '{"state":"RUNNING"}' >/dev/null

step "3. Discover"
D=$(curl -sf -X POST "$API_BASE/pipeline/discover" -H 'Content-Type: application/json' \
  -d "{\"brand\":\"$BRAND\",\"sources\":[\"hackernews\"],\"limit_per_source\":5}")
CREATED=$(echo "$D" | jsonq "['created']"); echo "discovered: $CREATED (+$(echo "$D" | jsonq "['duplicates']") dup)"

step "4. Opportunities listed"
OPPS=$(curl -sf "$API_BASE/opportunities?limit=5")
N=$(echo "$OPPS" | jsonq "[0]['topic']" >/dev/null 2>&1 && echo has || echo none)
echo "opportunities: $N"

step "5. Score top opportunity"
OPP_ID=$(echo "$OPPS" | jsonq "[0]['id']")
if [ "$OPP_ID" != "" ] && [ "$OPP_ID" != "None" ]; then
  SC=$(curl -sf -X POST "$API_BASE/pipeline/score" -H 'Content-Type: application/json' -d "{
    \"opportunity_id\":\"$OPP_ID\",
    \"factors\":{\"TrendVelocity\":80,\"AudienceFit\":70,\"ViralPotential\":60,\"ContentGap\":75,
                \"Freshness\":90,\"Monetization\":50,\"ProductionEase\":85,\"Confidence\":80},
    \"penalties\":{\"RiskPenalty\":2,\"SaturationPenalty\":3}}")
  TOTAL=$(echo "$SC" | jsonq "['total']"); echo "score total: $TOTAL"
  check "score recorded" "True" "$([ "$TOTAL" != "" ] && [ "$TOTAL" != "None" ] && echo True || echo False)"
else
  echo "SKIP: no opportunities (discovery offline?)"
fi

step "Summary"
echo "PASS=$PASS FAIL=$FAIL"
[ "$FAIL" -eq 0 ]
