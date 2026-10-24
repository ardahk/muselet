#!/usr/bin/env bash
# Heartbeat: every $INTERVAL seconds (1) snapshot local work to wip/local and, if main, wip/* or cloud/* moved,
# message every reviewer in runs/reviewers.json; (2) log Tinker month-to-date spend and, at the phase cap
# ($60) or near the hard cap ($135 of $150), tell the training session (once per level) to pause / stop.
set -uo pipefail
cd "$(git rev-parse --show-toplevel)"
INTERVAL=${INTERVAL:-900}
TRAINING_SESSION=${TRAINING_SESSION:-25d3d0c17f9e454f8078f13d3b4f00ea}
state=runs/review_pulse.state
guard_state=runs/tinker_guard.state
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
  spend=$(python3 tools/tinker_spend.py --log runs/tinker_spend.jsonl --guard); level=$?
  echo "$(date +%T) tinker $spend" | cut -c1-200
  if [ "$level" -ge 2 ] && [ "$level" -gt "$(cat "$guard_state" 2>/dev/null || echo 0)" ]; then
    if [ "$level" -eq 3 ]; then
      text="SPEND GUARD (automatic, from the lead's machine): Tinker month-to-date spend is at \$140 of the \$150 hard cap: $spend. Stop all Tinker training and sampling now, save checkpoints, and report. Do not start anything new without lead approval."
    else
      text="SPEND GUARD (automatic, from the lead's machine): Tinker month-to-date spend reached \$120 of the \$150 hard cap: $spend. Finish or checkpoint the current step, do not start any new Tinker job, and report spend and status for lead approval."
    fi
    python3 tools/devin_cloud.py msg "$TRAINING_SESSION" --text "$text" >/dev/null && echo "$level" > "$guard_state" && echo "$(date +%T) spend guard level $level sent"
  fi
  sleep "$INTERVAL"
done
