#!/usr/bin/env bash
# Memory guard for local agent work on the user's Mac. Every 5 s reads the kernel's free-memory level (percent).
# < 25%: SIGTERM benchmark/secondary model processes started by agents. < 15%: also the secondary :8766 brain.
# Never touches user apps, Muselet.app, or the main :8765 brain.
set -uo pipefail
cd "$(git rev-parse --show-toplevel)"
log=runs/mem_guard.log
HEAVY='mlx_vlm|run_screenspot|bench/systemone|deskmind-brain-serve|speed_lab.py|run_jevbench|run_typed_decisions|jevbench.cli|mlx_lm.(generate|server|convert)'
while true; do
  lvl=$(sysctl -n kern.memorystatus_level 2>/dev/null || echo 100)
  if [ "$lvl" -lt 25 ]; then
    pids=$(pgrep -f -E "$HEAVY" | tr '\n' ' ')
    if [ "$lvl" -lt 15 ]; then
      pids="$pids $(lsof -t -iTCP:8766 -sTCP:LISTEN 2>/dev/null | tr '\n' ' ')"
    fi
    if [ -n "${pids// /}" ]; then
      echo "$(date +%T) free=${lvl}% killing: $pids" >> "$log"
      kill $pids 2>/dev/null
    fi
  fi
  sleep 5
done
