# bench digest — pass 27 (2026-10-24T12:10Z, main@d7c192f)

P0: 0 | open P1: 8 | open P2: 2

## Open P1 (ranked)
1. bench-22 — Eval-overlap normalization deletes all CJK, so DeskMind overlap is unmeasurable — `training/src/muselet_train/decontam.py:26-27` (cloud/data-pipeline@0ce9ea6)
1b. bench-16 — Per-run safety skips give the two systems different task denominators — `bench/hobbylm/replay.py` (main)
2. bench-20 — Timer tasks graded for Muselet but always ungradable for HobbyLM — `bench/hobbylm/replay.py` (main@d502b78)
3. bench-21 — Calculator tasks start pre-opened for Muselet, quit for HobbyLM — `bench/hobbylm/replay.py` (main@d502b78)
4. bench-11 — Non-MLX backends (fake, Tinker) report as 'muselet' — `bench/systemone/cli.py` (main)
5. bench-18 — 'main' router run trained on route_dedup.jsonl with unrecorded eval filtering — `training/src/muselet_train/evalcheck.py` (measured: r2 15/125 HobbyLM r4 near-dups, it2 0; it2 now served)
6. bench-15 — Grounding subset in pitch/claims.md not reproducible (--limit is a sorted prefix; no stratified sampler committed; ±6.7 pt at n=200) — `bench/grounding/run_screenspot.py` (main)
7. bench-14 — No ScreenSpot-Pro/OSWorld-G decontamination for grounding training data — `training/src/muselet_train/decontam.py` (branch-only)

Open P2: bench-12 (chunked choice probabilities), bench-19 (claims.md quotes consumed holdout-1, n=14, overlapping CIs; use holdout2 + CI).

## Highest-leverage next moves
- hobby-gaps is merged: forward HobbyLM's recorded timers to its grade (bench-20; the Muselet side now uses the timers RPC) and give both systems the same Calculator start state (bench-21).
- Intersect eligible (id, repeat) across systems in report_math before any headline (bench-16).
- Accept only --backend mlx results for Muselet headlines (bench-11).
- Re-run evalcheck (now with evals/external) on main-final and it2 datums and commit the reports before quoting their HobbyLM/DeskMind scores; quote route numbers on route_v1_clean (bench-18).
- Build the ScreenSpot-Pro/OSWorld-G manifest before any grounding data generation (bench-14).
- Commit the stratified ScreenSpot-Pro sampler + sample IDs and report CIs before the grounding numbers go in the pitch (bench-15).
- Fix CJK normalization in decontam/evalcheck and re-run before any trained-router DeskMind claim (bench-22); quote HobbyLM r4 with it2, never r2 (bench-18).
