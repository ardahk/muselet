#!/usr/bin/env bash
# Build + (re)launch app/build/Muselet.app.
#   bash app/scripts/run_app.sh
# Start the brain separately:  cd <repo> && uv run --project ml brain serve
# Logs: ~/Library/Logs/Muselet/muselet.log  (and `log stream --predicate 'process == "Muselet"'`)
set -euo pipefail
APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
bash "$APP_DIR/scripts/build_app.sh"
# Quit a running instance so the fresh build takes over.
if pgrep -x Muselet >/dev/null 2>&1; then
  osascript -e 'tell application id "ai.muselet.app" to quit' >/dev/null 2>&1 || true
  for _ in $(seq 1 20); do pgrep -x Muselet >/dev/null 2>&1 || break; sleep 0.1; done
  pkill -x Muselet 2>/dev/null || true
fi
open "$APP_DIR/build/Muselet.app"
echo "==> launched muselet (menu bar). Log: ~/Library/Logs/Muselet/muselet.log"
