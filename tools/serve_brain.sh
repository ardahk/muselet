#!/usr/bin/env bash
# Recommended brain configuration (lead's call, Sat Oct 24; every option stays selectable by env/flags):
#   router  = cloud A's trained 4B router, fixed export r2 (models/route-4b-main-mlx4-r2, rev 2e3e7bf) when present,
#             else base Qwen3.5-4B-4bit. r1 (models/route-4b-main-mlx4) stays selectable via ROUTER=...
#   ARGS    = the router itself when it is r2 (val ARGS exact .854 vs base .521 on the same items; route_v1 r2 self
#             1.000 pending a contamination check), base 4B otherwise (r1's merged export had a broken head)
#   tau     = val-fitted per router (r2 .45, r1 .55, base .20; evals/router_check.py)
#   planner = base 4B, few-shot + DSL history + line-start constraint + done-alone (offline planner bench, tune+holdout)
#   ESCALATE=1 adds Qwen3.6-35B-A3B as the escalation planner (~19 GB resident; off by default)
# Usage: tools/serve_brain.sh [extra brain serve flags]   (PORT, ROUTER, ARGS_MODEL, PLANNER, TAU, ESCALATE env)
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
BASE=mlx-community/Qwen3.5-4B-4bit
R1=models/route-4b-main-mlx4
R2=models/route-4b-main-mlx4-r2
if [ -z "${ROUTER:-}" ]; then
  if [ -f "$R2/config.json" ]; then ROUTER=$R2; elif [ -f "$R1/config.json" ]; then ROUTER=$R1; else ROUTER=$BASE; fi
fi
case "$ROUTER" in
  "$R2") TAU=${TAU:-0.45}; ARGS_MODEL=${ARGS_MODEL:-$R2} ;;
  "$R1") TAU=${TAU:-0.55}; ARGS_MODEL=${ARGS_MODEL:-$BASE} ;;
  *)     TAU=${TAU:-0.20}; ARGS_MODEL=${ARGS_MODEL:-$BASE} ;;
esac
args=(--port "${PORT:-8765}" --model "$ROUTER" --tau "$TAU" --args-model "$ARGS_MODEL"
      --planner-model "${PLANNER:-$BASE}")
if [ "${ESCALATE:-0}" = "1" ]; then args+=(--planner-escalate-model mlx-community/Qwen3.6-35B-A3B-4bit); fi
exec uv run --project ml brain serve "${args[@]}" "$@"
