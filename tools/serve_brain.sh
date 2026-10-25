#!/usr/bin/env bash
# Recommended brain configuration (lead's call, Sat Oct 24; every option stays selectable by env/flags):
#   router  = cloud A's iteration-2 router it2 (models/route-4b-it2-mlx4, rev 54b2181) when present, else r2
#             (models/route-4b-main-mlx4-r2, rev 2e3e7bf), else base Qwen3.5-4B-4bit; r1 stays selectable via ROUTER=...
#             it2 vs r2: val top-1 .938 vs .912, val ARGS .869 vs .854; clean route_v1 (103) acc .913 vs .864, e2e .857 both
#   ARGS    = the router itself when it is r2 (val ARGS exact .854 vs base .521 on the same items; route_v1 r2 self
#             1.000 pending a contamination check), base 4B otherwise (r1's merged export had a broken head)
#   tau     = val-fitted per router (it2 .35, it3 .50 on the it3 val set by evals/router_check.py, macro-F1; was it2 .65;
#             r2 .45, r1 .55, base .20). it2 @ .35: route_v1_clean .942, route_v2 .838; it3 @ .50: .922 / .945, ARGS .855 vs
#             .856, parity top-1 .983. it3 is the default (user, Sat evening: +10.7 on the 955-request set outweighs -2.0 on
#             the 103 clean cases; the pre-registered rule would have kept it2). ROUTER=it2 restores it2 @ .35
#   planner = LoRA 4B, no few-shot, retrieval k=1, THINK=0: v1-ho/v1-ho2/v2-ho
#             .857/1.000/.692, mean .850, step p50 ~0.3 s (ships by the pre-registered rule).
#             Reference: (a) LoRA k=0 .857/1.000/.623; (c) LoRA + few-shot + k=1 + THINK=512
#             .857/.833/.646; base + few-shot + k=1 + THINK=512 .786/.917/.608, mean .770 @ 2.6 s.
#             PLANNER=base keeps the base planner selectable; PLANNER=lora selects the LoRA.
#   retrieval = 1 BM25-retrieved solved example from the v2-tune bank (RETRIEVAL_K=0|1|2; default 1 for base and LoRA).
#             The earlier base-planner comparison was mean holdout .570 -> .642 for k=0 / k=1, with TTFT +44..72 ms;
#             k=2 failed the +150 ms TTFT gate (cloud/handoff/notes/retrieval_eval.md)
#   think   = THINK=512 (qwen sampler) is now the base-planner default only; the shipped LoRA uses THINK=0.
#   aux     = base 4B for every non-DSL generation/decide so the LoRA only plans; +1 resident 4B ~= 2.5 GB;
#             PLANNER_AUX=planner reuses the planner.
#             Download the LoRA:
#             uv run --project ml python -c "from huggingface_hub import snapshot_download as d; d('jonsnov/muselet-planner-4b-lora-mlx4', revision='35a2ea331919c82114ebfda7b76dbfba663bbc58', local_dir='models/planner-4b-lora-mlx4')"
#   it3     = ROUTER=it3 (models/route-4b-it3-mlx4 = jonsnov/muselet-route-4b-it3-mlx4 @ e057412), default router: routes over
#             catalog v3 (training/artifacts/catalog_v3.json, 43 options) via MUSELET_ROUTE_CATALOG
#             (router + ARGS only; orchestrator/planner keep skills/catalog.json); tau .50 (val fit). ROUTER also takes it2|r2|r1|base.
#   ESCALATE=1 adds Qwen3.6-35B-A3B as the escalation planner (~19 GB resident; off by default)
#   memory  = working memory rules + long-term store on; LLM rewrite off (MEMORY_LLM=1 turns it on). Holdout
#             (evals/memory_eval.py): rules+lt resolution .574, false-rewrite .0195; +LLM .670 but false-rewrite .078
#             (ship rule .85 / .02 not met by any mode)
#   verify-done = done needs a passing expect or a model check on a fresh observation; VERIFY_DONE=off restores the old rule
#   fallback = a recoverable skill/brain-tool failure hands the goal once to the planner with the failure as Last batch (FALLBACK_PLANNER=0 restores the error bubble); PLANNER_CONTEXT=1 adds ctx app/window/url + a screen summary (OCR when AX is thin) to the planner's first turn
#   open-ended = APP_HINTS/OPEN_ENDED route free-form asks to the planner's open-ended path
# Usage: PORT=... ROUTER=... ARGS_MODEL=... PLANNER=... FEWSHOT=... PLANNER_AUX=... TAU=... RETRIEVAL_K=... THINK=... THINK_ON=... THINK_SAMPLER=... APP_HINTS=... OPEN_ENDED=... ESCALATE=... VERIFY_DONE=... FALLBACK_PLANNER=... PLANNER_CONTEXT=... MEMORY=... MEMORY_LLM=... LONGTERM=... tools/serve_brain.sh [extra brain serve flags]
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
# Brains on any port but the app's :8765 (benchmarks) get a fresh memory store per start, so test utterances never
# reach the user's long-term memory and no case inherits memories from another run.
if [ "${PORT:-8765}" != "8765" ] && [ -z "${MUSELET_MEMORY_DB:-}" ]; then
  export MUSELET_MEMORY_DB="$PWD/runs/memory/bench-${PORT}-$(date +%Y%m%dT%H%M%S)/memory.db"
  mkdir -p "$(dirname "$MUSELET_MEMORY_DB")"
fi
BASE=mlx-community/Qwen3.5-4B-4bit
LORA=models/planner-4b-lora-mlx4
R1=models/route-4b-main-mlx4
R2=models/route-4b-main-mlx4-r2
IT2=models/route-4b-it2-mlx4
IT3=models/route-4b-it3-mlx4
case "${ROUTER:-}" in it2) ROUTER=$IT2 ;; it3) ROUTER=$IT3 ;; r2) ROUTER=$R2 ;; r1) ROUTER=$R1 ;; base) ROUTER=$BASE ;; esac
BIG=mlx-community/Qwen3.6-35B-A3B-4bit
case "${PLANNER:-}" in lora) PLANNER=$LORA ;; base) PLANNER=$BASE ;; 35b) PLANNER=$BIG; BLIND_PLANNER=${BLIND_PLANNER:-planner}; export MUSELET_OBS_NODES=${MUSELET_OBS_NODES:-350} ;; esac
if [ -z "${ROUTER:-}" ]; then
  if [ -f "$IT3/config.json" ]; then ROUTER=$IT3; elif [ -f "$IT2/config.json" ]; then ROUTER=$IT2; elif [ -f "$R2/config.json" ]; then ROUTER=$R2; elif [ -f "$R1/config.json" ]; then ROUTER=$R1; else ROUTER=$BASE; fi
fi
if [ -z "${PLANNER:-}" ]; then
  if [ -f "$LORA/config.json" ]; then PLANNER=$LORA; else PLANNER=$BASE; fi
fi
case "$PLANNER" in
  "$LORA") THINK=${THINK:-0}; FEWSHOT=${FEWSHOT:-none} ;;
  *)        THINK=${THINK:-512}; FEWSHOT=${FEWSHOT:-prompts/planner_fewshot.md} ;;
esac
case "$ROUTER" in
  "$IT2") TAU=${TAU:-0.35}; ARGS_MODEL=${ARGS_MODEL:-$IT2} ;;
  "$IT3") TAU=${TAU:-0.50}; ARGS_MODEL=${ARGS_MODEL:-$IT3}; export MUSELET_ROUTE_CATALOG=${MUSELET_ROUTE_CATALOG:-$PWD/training/artifacts/catalog_v3.json} ;;
  "$R2") TAU=${TAU:-0.45}; ARGS_MODEL=${ARGS_MODEL:-$R2} ;;
  "$R1") TAU=${TAU:-0.55}; ARGS_MODEL=${ARGS_MODEL:-$BASE} ;;
  *)     TAU=${TAU:-0.20}; ARGS_MODEL=${ARGS_MODEL:-$BASE} ;;
esac
fallback_planner=${FALLBACK_PLANNER:-1}
case "$fallback_planner" in 1|on) fallback_planner=on ;; 0|off) fallback_planner=off ;; esac
planner_context=${PLANNER_CONTEXT:-1}
case "$planner_context" in 1|on) planner_context=on ;; 0|off) planner_context=off ;; esac
args=(--port "${PORT:-8765}" --model "$ROUTER" --tau "$TAU" --args-model "$ARGS_MODEL"
      --planner-model "$PLANNER" --planner-fewshot "$FEWSHOT"
      --planner-aux-model "${PLANNER_AUX:-$BASE}"
      --planner-retrieval-k "${RETRIEVAL_K:-1}"
      --planner-app-hints "$([ "${APP_HINTS:-1}" = "0" ] && echo off || echo on)"
      --open-ended-route "$([ "${OPEN_ENDED:-1}" = "0" ] && echo off || echo on)"
      --agentic-apps "$([ "${AGENTIC_APPS:-1}" = "0" ] && echo off || echo on)"
      --planner-blind "${BLIND_PLANNER:-$(
        [ -d "$HOME/.cache/huggingface/hub/models--mlx-community--Qwen3.6-35B-A3B-4bit" ] \
          && echo escalate || echo base)}"
      --planner-think "$THINK" --planner-think-on "${THINK_ON:-all}"
      --planner-think-sampler "${THINK_SAMPLER:-qwen}"
      --verify-done "${VERIFY_DONE:-on}"
      --fallback-planner "$fallback_planner"
      --planner-context "$planner_context")
# grounder: the local MLX copy (never a multi-GB lazy download mid-request); GROUNDER=name[=path]|none overrides
if [ -n "${GROUNDER:-}" ]; then args+=(--grounder-model "$GROUNDER")
elif [ -f models/grounding/eyes-4b-mlx/config.json ]; then args+=(--grounder-model eyes-4b=models/grounding/eyes-4b-mlx); fi
if [ "${ESCALATE:-0}" = "1" ]; then args+=(--planner-escalate-model mlx-community/Qwen3.6-35B-A3B-4bit); fi
if [ "${MEMORY:-1}" = "0" ]; then args+=(--no-memory); fi
if [ "${MEMORY_LLM:-0}" = "0" ]; then args+=(--no-memory-llm); fi
if [ "${LONGTERM:-1}" = "0" ]; then args+=(--no-longterm); fi
exec uv run --project ml brain serve "${args[@]}" "$@"
