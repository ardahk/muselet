# bench digest — pass 43 (2026-10-24T21:58Z, main@3772f7c)

P0: 0 | open P1: 8 | open P2: 8

## Open P1 (ranked)
1. bench-16 — Per-run safety skips give the two systems different task denominators — `bench/hobbylm/replay.py` (main)
2. bench-20 — Timer tasks graded for Muselet but always ungradable for HobbyLM — `bench/hobbylm/replay.py` (main@d502b78)
3. bench-21 — Calculator tasks start pre-opened for Muselet, quit for HobbyLM — `bench/hobbylm/replay.py` (main@d502b78)
4. bench-11 — Non-MLX backends (fake, Tinker) report as 'muselet' — `bench/systemone/cli.py` (main)
5. bench-15 — Grounding subset in pitch/claims.md not reproducible (--limit is a sorted prefix; no stratified sampler committed; ±6.7 pt at n=200) — `bench/grounding/run_screenspot.py` (main)
6. bench-28 — Planner v2 gold/accept rewards `type "\n…"` appends that replace the field (5 holdout + 3 tune cases) — `evals/planner_scenarios_v2.jsonl` (main)
7. bench-29 — Retrieval bank shows v2-holdout the identical tune screen (19/130 top-1, 0 directly copyable); k=1 now SHIPPED on main@3772f7c without a same-screen slice — `ml/src/brain/plan_bank.py` (main)
8. bench-14 — No ScreenSpot-Pro/OSWorld-G decontamination for grounding training data — `training/src/muselet_train/decontam.py` (branch-only)

Open P2: bench-30 (retrieval '+7.2 pts' = unweighted mean where two n<=14 sets moved by 1 scenario each; v2-holdout alone +6.2, unpaired), bench-26 (planner v2 tune/holdout share 14 screens; exact-goal split check only; now on main via #29; measured: 21 demo states reuse 12 holdout observations), bench-25 (live T1 86.4% over ran cases; 8 eligible T1 skipped at runtime, reasons untracked; live_t1 edited on main@fb2cfd0 and graders changed on 7065dd3 after that run, incl. a post-hoc volume band widening; no suite hash; claims.md/REPORT.md on main now quote that pre-change run via #26), bench-23 (route_v2 gold judge = it3 relabel judge; hard items dropped), bench-24 (evalcheck skips missing eval files), bench-22 (route evalcheck fixed on data-pipeline@512cce0; only the decisions decontam tokenizer still drops CJK; it has now run on the full decisions data, e125c13), bench-12 (chunked choice probabilities), bench-19 (claims.md quotes consumed holdout-1, n=14, overlapping CIs; use holdout2 + CI).

## Highest-leverage next moves
- Intersect the k0->k1 v2-holdout flips (runs/planner_offline/ret_k{0,1}_v2ho.json) with the 19 same-screen ids from reviews/bench/tests/retrieval_leak_pass43.py; quote v2-holdout with paired W/L, not the 3-set mean (bench-29, bench-30).
- Fix the 8 clobbering v2 gold/accept rules and add a clobber reject to planner_offline.grade before quoting v2-holdout (bench-28).
- Make teachers.py refuse non-v2-tune states and record input sha256 + split in meta.json before any planner demo generation/upload; split v2 by screen first (bench-26). bench-27 resolved on planner-demos@9008990 (build_states takes v2-tune only + gate).
- hobby-gaps is merged: forward HobbyLM's recorded timers to its grade (bench-20; the Muselet side now uses the timers RPC) and give both systems the same Calculator start state (bench-21).
- Intersect eligible (id, repeat) across systems in report_math before any headline (bench-16).
- Accept only --backend mlx results for Muselet headlines (bench-11).
- Build the ScreenSpot-Pro/OSWorld-G manifest before any grounding data generation (bench-14).
- Commit the stratified ScreenSpot-Pro sampler + sample IDs and report CIs before the grounding numbers go in the pitch (bench-15).
- Reuse the CJK-aware norm in training/decisions/decontam.py (bench-22).
