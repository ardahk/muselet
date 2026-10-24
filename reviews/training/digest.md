# training review digest: pass 13
_heads: main 280715d, wip/local 38768f3 (=main in lane), cloud/data-pipeline 1d65818 (eval_route + parity key fix); other cloud/* unchanged_

## Open P0/P1 (ranked)
- **training-5** [P1] The billing guard lags by hours and the per-run --max-usd ignores cumulative spend, so a run can cross $150; no billed figure is recorded yet (`tools/tinker_spend.py`, `training/src/muselet_train/train.py`).
- **training-14** [P1] main has catalog v2 but 36-option parity samples, so the parity test xfails while the pitch claims token-identical rendering (`training/artifacts/route_render_samples.jsonl`, `pitch/devpost.md:45`).
- **training-17** [P1] In the pilots, finance_review val accuracy is 0–25%; it's a demo-critical skill (`training/reports/phase1_pilot-lr4e-4.md`).
- **training-8** [P1] No per-label 15% adjudication STOP gate, and the per-row A1 trigger is narrower than SPEC (`training/src/muselet_train/adjudicate.py`).
- **training-15** [P1] The stratified teacher subset skews the label prior and mixes hard and soft targets (`training/src/muselet_train/teacher.py`).
- **training-11** [P1] Finder selection=yes can't happen at runtime, but constrain() forces it for copy_selection (`training/src/muselet_train/contexts.py`).

Resolved this pass: training-21. Open P2: training-9, -10 (downgraded: decontam verified in phase1_fixes.md), -12, -13, -18, -19, -20, -22 (val eval without --teacher-files drops ASK).

## Highest-leverage next moves
1. Before the main run on v2all (41.9K route / 27.9K ARGS before dedup), record the `tinker billing` figure and set --max-usd to at most 150 minus billed minus the estimates for unbilled runs (training-5).
2. Pass the trainer's --teacher-files to eval_route/parity (training-22); merge PR #2's 41-option render artifact to main so the parity test passes before the pitch claims parity (training-14).
3. Run the main run with --final-full-val and check finance_review per_label_n and accuracy (training-17).
4. Add the 15% A1 STOP and re-score the 1,885 constrained-context rows with the teacher (training-8, training-20).
5. Save sampler weights at each eval and export the best-val step, not the last (training-18).
