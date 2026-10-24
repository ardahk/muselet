# bench digest — pass 16 (2026-10-24T09:20Z, main@2920225)

P0: 0 | open P1: 4 | open P2: 3

## Open P1 (ranked)
1. bench-16 — Per-run safety skips give the two systems different task denominators — `bench/hobbylm/replay.py` (main)
2. bench-11 — Non-MLX backends (fake, and Tinker on cloud/decisions) report as 'muselet' — `bench/systemone/cli.py` (main)
3. bench-18 — 'main' router run trained on route_dedup.jsonl with unrecorded eval filtering — `training/src/muselet_train/datums_export.py` (cloud/data-pipeline)
4. bench-14 — No ScreenSpot-Pro/OSWorld-G decontamination for grounding training data — `training/src/muselet_train/decontam.py` (branch-only, cloud/data-pipeline)

Open P2: bench-12 (chunked choice probabilities can contradict the stage-two winner), bench-15 (grounding --limit takes a single-app prefix), bench-19 (planner knobs tuned and selected on the same small set).
Retracted: bench-17 (dedup.py does write route_train/val after the eval filter).

## Highest-leverage next moves
- Intersect eligible (id, repeat) across systems in HobbyLM report_math before publishing any headline (bench-16).
- Make Muselet headline publishers accept only --backend mlx results; derive model_name from the backend (bench-11).
- Re-run the current eval filter on the `main` run's route_dedup.jsonl and publish the overlap count before quoting its scores (bench-18).
- Build the ScreenSpot-Pro/OSWorld-G instruction + pHash manifest before any grounding data generation (bench-14).
- Add a holdout split and Wilson CIs to evals/planner_offline.py before choosing a planner (bench-19).
