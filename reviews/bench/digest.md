# bench digest — pass 36 (2026-10-24T19:20Z, main@e56582b)

P0: 0 | open P1: 6 | open P2: 7

## Open P1 (ranked)
1. bench-16 — Per-run safety skips give the two systems different task denominators — `bench/hobbylm/replay.py` (main)
2. bench-20 — Timer tasks graded for Muselet but always ungradable for HobbyLM — `bench/hobbylm/replay.py` (main@d502b78)
3. bench-21 — Calculator tasks start pre-opened for Muselet, quit for HobbyLM — `bench/hobbylm/replay.py` (main@d502b78)
4. bench-11 — Non-MLX backends (fake, Tinker) report as 'muselet' — `bench/systemone/cli.py` (main)
5. bench-15 — Grounding subset in pitch/claims.md not reproducible (--limit is a sorted prefix; no stratified sampler committed; ±6.7 pt at n=200) — `bench/grounding/run_screenspot.py` (main)
6. bench-14 — No ScreenSpot-Pro/OSWorld-G decontamination for grounding training data — `training/src/muselet_train/decontam.py` (branch-only)

Open P2: bench-26 (planner v2 tune/holdout share 14 screens; exact-goal split check only), bench-25 (live T1 86.4% over ran cases; 8 eligible T1 skipped at runtime, reasons untracked), bench-23 (route_v2 gold judge = it3 relabel judge; hard items dropped), bench-24 (evalcheck skips missing eval files), bench-22 (route evalcheck fixed on data-pipeline@512cce0; only the decisions decontam tokenizer still drops CJK; it has now run on the full decisions data, e125c13), bench-12 (chunked choice probabilities), bench-19 (claims.md quotes consumed holdout-1, n=14, overlapping CIs; use holdout2 + CI).

## Highest-leverage next moves
- hobby-gaps is merged: forward HobbyLM's recorded timers to its grade (bench-20; the Muselet side now uses the timers RPC) and give both systems the same Calculator start state (bench-21).
- Intersect eligible (id, repeat) across systems in report_math before any headline (bench-16).
- Accept only --backend mlx results for Muselet headlines (bench-11).
- Build the ScreenSpot-Pro/OSWorld-G manifest before any grounding data generation (bench-14).
- Commit the stratified ScreenSpot-Pro sampler + sample IDs and report CIs before the grounding numbers go in the pitch (bench-15).
- Reuse the CJK-aware norm in training/decisions/decontam.py (bench-22).
