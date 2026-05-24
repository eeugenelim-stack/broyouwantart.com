#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
PORT=8765
URL="http://127.0.0.1:${PORT}/?monolith=v2&drawn=1"

if lsof -nP -iTCP:${PORT} -sTCP:LISTEN >/dev/null 2>&1; then
  echo "Local preview server is already running on port ${PORT}."
else
  echo "Starting local preview server on port ${PORT}..."
  python3 -m http.server "${PORT}" --bind 127.0.0.1 >/tmp/broyouwantart-local-preview.log 2>&1 &
  echo $! > /tmp/broyouwantart-local-preview.pid
  sleep 1
fi

echo "Opening ${URL}"
open "${URL}"
echo ""
echo "Preview URL: ${URL}"
echo "Server log: /tmp/broyouwantart-local-preview.log"
echo "To stop the preview server later, run: kill $(cat /tmp/broyouwantart-local-preview.pid 2>/dev/null || echo PID)"
