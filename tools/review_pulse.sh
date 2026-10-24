#!/usr/bin/env bash
# Reviewer heartbeat: every $INTERVAL seconds snapshot local work to wip/local; if main, wip/* or cloud/*
# moved since the last pulse, message every reviewer session listed in runs/reviewers.json.
set -uo pipefail
cd "$(git rev-parse --show-toplevel)"
INTERVAL=${INTERVAL:-900}
state=runs/review_pulse.state
while true; do
  tools/push_wip.sh || echo "$(date +%T) wip push failed"
  git fetch -q --prune origin
  heads=$(git for-each-ref --format='%(refname:lstrip=3) %(objectname:short)' \
    refs/remotes/origin/main refs/remotes/origin/wip refs/remotes/origin/cloud)
  if [ "$heads" != "$(cat "$state" 2>/dev/null)" ]; then
    msg=$(printf 'PULSE %s. Branch heads now:\n%s\nRun your next review pass over everything since your last reviewed SHA per branch (also re-check your open findings), push your review branch, reply with the short summary, then end your turn.' "$(date -u +%FT%TZ)" "$heads")
    for id in $(python3 -c 'import json;print(" ".join(r["session_id"] for r in json.load(open("runs/reviewers.json"))))'); do
      python3 tools/devin_cloud.py msg "$id" --text "$msg" >/dev/null && echo "$(date +%T) pulsed $id"
    done
    echo "$heads" > "$state"
  fi
  sleep "$INTERVAL"
done
