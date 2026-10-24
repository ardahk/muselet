# training review digest: pass 10
_heads: main 4a74659 (PRs #5/#6/#7/#9/#10 merged), wip/local 85c73ed, cloud/data-pipeline 9c526b1 (adds phase1_fixes report), bench c3ca0b3; other branches unchanged_

## Open P0/P1 (ranked)
- **training-5** [P1] Phase 1 spend is unverified (no billed figure for any run), and training alone (about $38.4) exceeds TRAIN_RESERVE $35 (`training/src/muselet_train/train.py`).
- **training-14** [P1] main has catalog v2 but 36-option parity samples, so the parity test xfails while the pitch claims token-identical rendering (`training/artifacts/route_render_samples.jsonl`, `pitch/devpost.md:45`).
- **training-17** [P1] In the pilots, finance_review val accuracy is 0–25%; it's a demo-critical skill (`training/reports/phase1_pilot-lr4e-4.md`).
- **training-8** [P1] No per-label 15% adjudication STOP gate, and the per-row A1 trigger is narrower than SPEC (`training/src/muselet_train/adjudicate.py`).
- **training-15** [P1] The stratified teacher subset skews the label prior and mixes hard and soft targets (`training/src/muselet_train/teacher.py`).
- **training-11** [P1] Finder selection=yes can't happen at runtime, but constrain() forces it for copy_selection (`training/src/muselet_train/contexts.py`).

Open P2: training-9, -10 (downgraded: decontam verified in phase1_fixes.md), -12, -13, -18, -19, -20.

## Highest-leverage next moves
1. Before the main run on v2all (41.9K route / 27.9K ARGS before dedup), record the `tinker billing` figure and set --max-usd to 60 minus billed spend (training-5).
2. Merge PR #2's 41-option render artifact to main so the parity test passes before the pitch claims parity (training-14).
3. Run the main run with --final-full-val and check finance_review per_label_n and accuracy (training-17).
4. Add the 15% A1 STOP and re-score the 1,885 constrained-context rows with the teacher (training-8, training-20).
5. Save sampler weights at each eval and export the best-val step, not the last (training-18).
