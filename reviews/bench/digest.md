# bench digest — pass 25 (2026-10-24T11:40Z, main@7147694)

P0: 0 | open P1: 6 | open P2: 3

## Open P1 (ranked)
1. bench-16 — Per-run safety skips give the two systems different task denominators — `bench/hobbylm/replay.py` (main)
2. bench-20 — Timer tasks graded for Muselet but always ungradable for HobbyLM — `bench/hobbylm/replay.py` (main@d502b78)
3. bench-21 — Calculator tasks start pre-opened for Muselet, quit for HobbyLM — `bench/hobbylm/replay.py` (main@d502b78)
4. bench-11 — Non-MLX backends (fake, Tinker) report as 'muselet' — `bench/systemone/cli.py` (main)
5. bench-18 — 'main' router run trained on route_dedup.jsonl with unrecorded eval filtering — `training/src/muselet_train/evalcheck.py` (cloud/data-pipeline@9b36081; gate covers evals/external; it2 marked non-candidate; main-final not re-run)
6. bench-14 — No ScreenSpot-Pro/OSWorld-G decontamination for grounding training data — `training/src/muselet_train/decontam.py` (branch-only)

Open P2: bench-12 (chunked choice probabilities), bench-15 (grounding --limit), bench-19 (holdout-1 consumed by rules 16-18; holdout2 n=12, still no CI).

## Highest-leverage next moves
- hobby-gaps is merged: forward HobbyLM's recorded timers to its grade (bench-20; the Muselet side now uses the timers RPC) and give both systems the same Calculator start state (bench-21).
- Intersect eligible (id, repeat) across systems in report_math before any headline (bench-16).
- Accept only --backend mlx results for Muselet headlines (bench-11).
- Re-run evalcheck (now with evals/external) on main-final and it2 datums and commit the reports before quoting their HobbyLM/DeskMind scores; quote route numbers on route_v1_clean (bench-18).
- Build the ScreenSpot-Pro/OSWorld-G manifest before any grounding data generation (bench-14).
