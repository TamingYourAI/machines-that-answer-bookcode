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
trap 'kill $server 2>/dev/null || true' EXIT
# Wait for the server, not for a fixed time: a cold CI runner can take far longer than a laptop.
for _ in $(seq 1 90); do
  if "${PW_PYTHON:-python3}" -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8089/healthz', timeout=1)" 2>/dev/null; then
    break
  fi
  if ! kill -0 "$server" 2>/dev/null; then
    echo "the server exited before it was ready:"; cat "$out/server.log"; exit 1
  fi
  sleep 1
done
"${PW_PYTHON:-python3}" -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8089/healthz', timeout=2)" \
  || { echo "the server never became ready:"; cat "$out/server.log"; exit 1; }
"${PW_PYTHON:-python3}" "$here/tests/browser/check_app.py" "$out" \
  || { echo "the browser check failed; the server's log follows:"; cat "$out/server.log"; exit 1; }
echo "screenshots in $out"
