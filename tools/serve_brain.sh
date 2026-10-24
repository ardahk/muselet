#!/usr/bin/env bash
# Recommended brain configuration (lead's call, Sat Oct 24; every option stays selectable by env/flags):
#   router  = cloud A's trained 4B router (models/route-4b-main-mlx4) when present, else base Qwen3.5-4B-4bit
#   ARGS    = base Qwen3.5-4B-4bit (the trained router's ARGS generation returns empty strings; route_v1 hybrid:
#             route acc .843 / F1 .904, args_exact .810, e2e .702 vs base .771 / .838 / .800 / .716)
#   tau     = val-fitted per router (trained .55, base .20; evals/router_check.py)
#   planner = base 4B, few-shot + DSL history + line-start constraint + done-alone (offline planner bench, tune+holdout)
#   ESCALATE=1 adds Qwen3.6-35B-A3B as the escalation planner (~19 GB resident; off by default)
# Usage: tools/serve_brain.sh [extra brain serve flags]   (PORT, ROUTER, ARGS_MODEL, PLANNER, TAU, ESCALATE env)
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
BASE=mlx-community/Qwen3.5-4B-4bit
TRAINED=models/route-4b-main-mlx4
if [ -z "${ROUTER:-}" ]; then
  if [ -f "$TRAINED/config.json" ]; then ROUTER=$TRAINED; else ROUTER=$BASE; fi
fi
if [ -z "${TAU:-}" ]; then
  if [ "$ROUTER" = "$TRAINED" ]; then TAU=0.55; else TAU=0.20; fi
fi
args=(--port "${PORT:-8765}" --model "$ROUTER" --tau "$TAU" --args-model "${ARGS_MODEL:-$BASE}"
      --planner-model "${PLANNER:-$BASE}")
if [ "${ESCALATE:-0}" = "1" ]; then args+=(--planner-escalate-model mlx-community/Qwen3.6-35B-A3B-4bit); fi
exec uv run --project ml brain serve "${args[@]}" "$@"
