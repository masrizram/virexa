#!/usr/bin/env bash
# Regenerate Fly deploy token and set it as GitHub secret in one pass (no clipboard).
set -e
cd "$(dirname "$0")/.."

FLY_TOKEN=$(flyctl tokens create deploy -a virexa-api 2>/dev/null)
[ -n "$FLY_TOKEN" ] || { echo "no fly token"; exit 1; }
echo "fly token len: ${#FLY_TOKEN}"

FLY_TOKEN="$FLY_TOKEN" PYTHONPATH= PYTHONHOME= apps/api/.venv/Scripts/python.exe scripts/set_gh_secret.py
