# bench digest — pass 51 (2026-10-25T00:05Z, main@0b83c3b)

P0: 0 | open P1: 10 | open P2: 8

## Open P1 (ranked)
1. bench-31 — Planner LoRA trained with ~21 v2-tune demos on v2-holdout screens; gate checks goals only — `training/planner_lora/common.py` (main@18c139f)
2. bench-34 — Think ship picks single-seed qwen (.770, p50 2596 ms) over greedy (.763, 1743 ms): net +1 scenario — `cloud/handoff/notes/planner_think_eval.md`
2b. bench-16 — HobbyLM replay: Muselet-only skips/--exclude-kind (calc = 30/125 of r4) shrink its denominator — `bench/hobbylm/replay.py`
3. bench-20 — Timer tasks graded for Muselet, ungradable for HobbyLM — `bench/hobbylm/replay.py`
4. bench-21 — Calculator starts in different initial states per arm — `bench/hobbylm/replay.py`
5. bench-29 — Retrieval bank exposes identical v2-holdout screens (19/130 top-1) — `ml/src/brain/plan_bank.py`
6. bench-28 — v2-holdout gold/accept still treats field-replacing type "\n..." as append (bank side fixed on main 7a85c1f) — `evals/planner_scenarios_v2.jsonl`
7. bench-11 — Non-MLX systemone backends report as `muselet` — `bench/systemone/`
8. bench-14 — No ScreenSpot-Pro/OSWorld-G decontam for grounding data — grounding pipeline
9. bench-15 — Grounding --limit is a sorted prefix, not a stratified sample — grounding runner

Open P2: bench-12, 19, 22, 23, 24, 25 (live graders changed after quoted run), 26, 30 (unweighted mean also in think rule).

## Highest-leverage next moves
- Think: serve greedy t512 unless qwen wins across >= 3 seeds (bench-34). It is about 850 ms per step faster at p50.
- HobbyLM r4: apply --exclude-kind to both arms, or report on the intersection of graded ids with excluded counts printed (bench-16).
- Planner-LoRA / think ship decisions: paired W/L on v2-holdout minus the 25 shared-screen rows (bench-31, 29, 30).
- Re-grade/re-run live T1 at 806b0d4 before quoting live numbers (bench-25).
- Fix the 5 clobbering v2-holdout golds and regrade k=0/k=1 before quoting v2-holdout (bench-28).
