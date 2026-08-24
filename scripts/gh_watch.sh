#!/usr/bin/env bash
# Poll GitHub Actions runs for masrizram/virexa until latest main run completes.
set -uo pipefail
GH=$(printf 'protocol=https\nhost=github.com\n\n' | git credential fill 2>/dev/null | grep -o '^password=.*' | cut -d= -f2)
for i in $(seq 1 60); do
  RUN=$(curl -s -m 20 -H "Authorization: Bearer $GH" \
    "https://api.github.com/repos/masrizram/virexa/actions/runs?branch=main&per_page=1")
  J=$(echo "$RUN" | python3 -c '
import sys, json
try:
    d = json.load(sys.stdin)["workflow_runs"][0]
    print(d["id"], d["status"], d["conclusion"], d["head_sha"][:7])
except Exception as e:
    print("ERR", e)')
  echo "[$i] $J"
  set -- $J
  if [ "$2" = "completed" ]; then
    echo "CONCLUSION=$3"; exit 0
  fi
  sleep 20
done
echo TIMEOUT
