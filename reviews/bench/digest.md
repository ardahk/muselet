# bench digest — pass 46 (2026-10-24T22:50Z, main@806b0d4)

P0: 0 | open P1: 9 | open P2: 9

## Open P1 (ranked)
1. bench-31 — Planner LoRA trained with ~21 v2-tune demos on v2-holdout screens; gate checks goals only — `training/planner_lora/common.py` (cloud/planner-lora)
2. bench-16 — HobbyLM replay: Muselet-only skips/--exclude-kind (calc = 30/125 of r4) shrink its denominator — `bench/hobbylm/replay.py`
3. bench-20 — Timer tasks graded for Muselet, ungradable for HobbyLM — `bench/hobbylm/replay.py`
4. bench-21 — Calculator starts in different initial states per arm — `bench/hobbylm/replay.py`
5. bench-29 — Retrieval bank exposes identical v2-holdout screens (19/130 top-1) — `ml/src/brain/plan_bank.py`
6. bench-28 — v2 gold/accept treats field-replacing type "\n..." as append — `evals/planner_offline.py`
7. bench-11 — Non-MLX systemone backends report as `muselet` — `bench/systemone/`
8. bench-14 — No ScreenSpot-Pro/OSWorld-G decontam for grounding data — grounding pipeline
9. bench-15 — Grounding --limit is a sorted prefix, not a stratified sample — grounding runner

Open P2: bench-12, 19, 22, 23, 24, 25 (live graders changed after quoted run), 26, 30 (unweighted mean also in think rule), 33 (claims rule text; fixed on docs-demo-2).

## Highest-leverage next moves
- HobbyLM r4: apply --exclude-kind to both arms, or report on the intersection of graded ids with excluded counts printed (bench-16).
- Planner-LoRA / think ship decisions: paired W/L on v2-holdout minus the 25 shared-screen rows (bench-31, 29, 30).
- Re-grade/re-run live T1 at 806b0d4 before quoting live numbers (bench-25).
- Merge docs-demo-2 so the claims match the code (bench-33).
