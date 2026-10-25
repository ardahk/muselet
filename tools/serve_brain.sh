#!/usr/bin/env bash
# Recommended brain configuration (lead's call, Sat Oct 24; every option stays selectable by env/flags):
#   router  = cloud A's iteration-2 router it2 (models/route-4b-it2-mlx4, rev 54b2181) when present, else r2
#             (models/route-4b-main-mlx4-r2, rev 2e3e7bf), else base Qwen3.5-4B-4bit; r1 stays selectable via ROUTER=...
#             it2 vs r2: val top-1 .938 vs .912, val ARGS .869 vs .854; clean route_v1 (103) acc .913 vs .864, e2e .857 both
#   ARGS    = the router itself when it is r2 (val ARGS exact .854 vs base .521 on the same items; route_v1 r2 self
#             1.000 pending a contamination check), base 4B otherwise (r1's merged export had a broken head)
#   tau     = val-fitted per router (it2 .65, r2 .45, r1 .55, base .20; evals/router_check.py)
#   planner = base 4B, few-shot + DSL history + line-start constraint + done-alone (offline planner bench, tune+holdout)
#   retrieval = 1 BM25-retrieved solved example from the v2-tune bank (RETRIEVAL_K=0|1|2): mean holdout pass .570 -> .642
#             (k=0 / k=1, v1-ho, v1-ho2, v2-ho), TTFT +44..72 ms; k=2 same gain but fails the +150 ms TTFT gate
#             (pre-registered rule; cloud/handoff/notes/retrieval_eval.md)
#   think   = planner thinking budget THINK=N tokens (default 0 = off until the Mac matrix passes the ship rule;
#             evals/planner_think_report.py); THINK_ON=all|retry, THINK_SAMPLER=greedy|qwen; ESCALATE inherits it
#   it3     = ROUTER=it3 (models/route-4b-it3-mlx4 = jonsnov/muselet-route-4b-it3-mlx4 @ e057412), opt-in only: routes over
#             catalog v3 (training/artifacts/catalog_v3.json, 43 options) via MUSELET_ROUTE_CATALOG
#             (router + ARGS only; orchestrator/planner keep skills/catalog.json); tau .65 is a placeholder
#             until the Mac val fit (evals/router_check.py --router it3 --set val). ROUTER also takes it2|r2|r1|base.
#   ESCALATE=1 adds Qwen3.6-35B-A3B as the escalation planner (~19 GB resident; off by default)
#   verify-done = done needs a passing expect or a model check on a fresh observation; VERIFY_DONE=off restores the old rule
# Usage: PORT=... ROUTER=... ARGS_MODEL=... PLANNER=... TAU=... RETRIEVAL_K=... THINK=... THINK_ON=... THINK_SAMPLER=... ESCALATE=... VERIFY_DONE=... MEMORY=... MEMORY_LLM=... LONGTERM=... tools/serve_brain.sh [extra brain serve flags]
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
BASE=mlx-community/Qwen3.5-4B-4bit
R1=models/route-4b-main-mlx4
R2=models/route-4b-main-mlx4-r2
IT2=models/route-4b-it2-mlx4
IT3=models/route-4b-it3-mlx4
case "${ROUTER:-}" in it2) ROUTER=$IT2 ;; it3) ROUTER=$IT3 ;; r2) ROUTER=$R2 ;; r1) ROUTER=$R1 ;; base) ROUTER=$BASE ;; esac
if [ -z "${ROUTER:-}" ]; then
  if [ -f "$IT2/config.json" ]; then ROUTER=$IT2; elif [ -f "$R2/config.json" ]; then ROUTER=$R2; elif [ -f "$R1/config.json" ]; then ROUTER=$R1; else ROUTER=$BASE; fi
fi
case "$ROUTER" in
  "$IT2") TAU=${TAU:-0.65}; ARGS_MODEL=${ARGS_MODEL:-$IT2} ;;
  "$IT3") TAU=${TAU:-0.65}; ARGS_MODEL=${ARGS_MODEL:-$IT3}; export MUSELET_ROUTE_CATALOG=${MUSELET_ROUTE_CATALOG:-$PWD/training/artifacts/catalog_v3.json} ;;
  "$R2") TAU=${TAU:-0.45}; ARGS_MODEL=${ARGS_MODEL:-$R2} ;;
  "$R1") TAU=${TAU:-0.55}; ARGS_MODEL=${ARGS_MODEL:-$BASE} ;;
  *)     TAU=${TAU:-0.20}; ARGS_MODEL=${ARGS_MODEL:-$BASE} ;;
esac
args=(--port "${PORT:-8765}" --model "$ROUTER" --tau "$TAU" --args-model "$ARGS_MODEL"
      --planner-model "${PLANNER:-$BASE}" --planner-retrieval-k "${RETRIEVAL_K:-1}"
      --planner-think "${THINK:-0}" --planner-think-on "${THINK_ON:-all}"
      --planner-think-sampler "${THINK_SAMPLER:-greedy}"
      --verify-done "${VERIFY_DONE:-on}")
if [ "${ESCALATE:-0}" = "1" ]; then args+=(--planner-escalate-model mlx-community/Qwen3.6-35B-A3B-4bit); fi
if [ "${MEMORY:-1}" = "0" ]; then args+=(--no-memory); fi
if [ "${MEMORY_LLM:-1}" = "0" ]; then args+=(--no-memory-llm); fi
if [ "${LONGTERM:-1}" = "0" ]; then args+=(--no-longterm); fi
exec uv run --project ml brain serve "${args[@]}" "$@"
