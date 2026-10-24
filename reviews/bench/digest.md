# bench digest — pass 21 (2026-10-24T10:40Z, main@d514300)

P0: 0 | open P1: 6 | open P2: 3

## Open P1 (ranked)
1. bench-16 — Per-run safety skips give the two systems different task denominators — `bench/hobbylm/replay.py` (main)
2. bench-20 — Timer tasks graded for Muselet but always ungradable for HobbyLM — `bench/hobbylm/replay.py` (cloud/hobby-gaps@929b931, unchanged)
3. bench-21 — Calculator tasks start pre-opened for Muselet, quit for HobbyLM — `bench/hobbylm/replay.py` (cloud/hobby-gaps@929b931, unchanged)
4. bench-11 — Non-MLX backends (fake, Tinker) report as 'muselet' — `bench/systemone/cli.py` (main)
5. bench-18 — 'main' router run trained on route_dedup.jsonl with unrecorded eval filtering — `training/src/muselet_train/datums_export.py` (cloud/data-pipeline)
6. bench-14 — No ScreenSpot-Pro/OSWorld-G decontamination for grounding training data — `training/src/muselet_train/decontam.py` (branch-only)

Open P2: bench-12 (chunked choice probabilities), bench-15 (grounding --limit), bench-19 (planner holdout added; still no CI).

## Highest-leverage next moves
- Before merging hobby-gaps: grade Muselet timers via the new `timers {}` RPC (cancel with `timers_cancel`) and forward HobbyLM's recorded timers (bench-20) and give both systems the same Calculator start state (bench-21).
- Intersect eligible (id, repeat) across systems in report_math before any headline (bench-16).
- Accept only --backend mlx results for Muselet headlines (bench-11).
- Publish the eval-overlap count for the `main` run's route_dedup.jsonl before quoting its scores (bench-18).
- Build the ScreenSpot-Pro/OSWorld-G manifest before any grounding data generation (bench-14).
