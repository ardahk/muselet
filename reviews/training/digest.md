# training lane digest — pass 17 (main 2920225, cloud/data-pipeline 5371185)

Open: 1 P0, 9 P1, 8 P2. Resolved this pass: training-11 (UtteranceCtx.swift:68-118@2920225 reports Finder item selection).
"branch-only" = code lives only on cloud/data-pipeline (PR #2, still unmerged into main).

## Open P0/P1 (ranked)
1. training-23 P0 — Main router trained/evaluated on stale pre-fix route data — main checkpoint (`evals/router_check.py:10`); new `datums_export.py --route-source dedup` can republish the stale rows for multi-task replay (branch-only code)
2. training-5 P1 — Shared Tinker cap ($81 headroom), lagging billing, per-run-only guard — `tools/tinker_spend.py`, `cloud/builder_decisions.md:57-58`; cloud/decisions@3a865a0 now has a Tinker backend
3. training-27 P1 — route_v1 tuned against but quoted as accuracy — `pitch/claims.md:13@2920225`, `training/reports/phase1_it2_plan.md`
4. training-14 P1 — Main parity reference still 36 options; parity test xfails while pitch claims byte-identical — `training/artifacts/route_render_samples.jsonl`
5. training-26 P1 — ASK rule treats pronoun values as concrete (fresh repro @5371185) — `training/src/muselet_train/ask_rule.py` (branch-only)
6. training-28 P1 — media_control sampled in Premiere Pro 7.9% — `training/src/muselet_train/contexts.py` (branch-only)
7. training-24 P1 — Router almost never ASKs (val 0/3) — `training/src/muselet_train/datums.py` (branch-only fix, not run)
8. training-25 P1 — Weak per-label val (media_control 32%, dark_mode 68%) — `training/reports/phase1_main.md`
9. training-8 P1 — No per-label 15% adjudication stop gate — `training/src/muselet_train/adjudicate.py` (branch-only)
10. training-15 P1 — Teacher subset skew / hard-soft mixing — `training/src/muselet_train/teacher.py` (branch-only)

## Highest-leverage next moves
- Merge PR #2's 41-option `route_render_samples.jsonl` (+ trainer) so main's parity test stops xfailing before the pitch claim ships.
- Before v2it2: fix pronoun ASK verdicts and block media_control in Premiere, then retrain from route_train/route_val (~$29) with `--pin-split-from`.
- Never export `--route-source dedup` for training; any decisions multi-task replay must use the split-based datums.
- One shared spend ledger for both Tinker workers: per-run cap = 150 − billed − unbilled estimates of both.
- Make a fresh held-out route set (or relabel route_v1 as dev) before quoting `{{route_acc}}`.
