#!/usr/bin/env bash
# Start a throwaway server with scripted hearing and the tone voice, then drive the app in
# Chromium. Usage: tests/browser/run.sh [output folder]
# OVA_PYTHON runs the server (needs the server extras); PW_PYTHON runs Playwright.
set -euo pipefail
here="$(cd "$(dirname "$0")/../.." && pwd)"
out="${1:-$(mktemp -d)}"
mkdir -p "$out"
data="$(mktemp -d)"
OVA_DATA_DIR="$data" OVA_PUBLIC_URL=http://127.0.0.1:8089 OVA_STT=script \
  OVA_STT_SCRIPT="my kitchen drain is blocked|12 Maple Street|Jordan|Wednesday|yes|no" \
  OVA_TTS=tones PYTHONPATH="$here/src" \
  "${OVA_PYTHON:-python}" -m uvicorn ova_server.app:dev_app --factory --host 127.0.0.1 --port 8089 \
  > "$out/server.log" 2>&1 &
server=$!
trap 'kill $server' EXIT
sleep 3
"${PW_PYTHON:-python3}" "$here/tests/browser/check_app.py" "$out"
echo "screenshots in $out"
