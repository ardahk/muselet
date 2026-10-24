# training review digest: pass 9
_heads: main d8ad966, wip/local 85ec0df, cloud/data-pipeline b8c0604 (review-fix commit), advisor-2 0a65f75, brain-2 741465c, finance-2 dfaf785, grounding 3441ee8, pitch ad1b058_

## Open P0/P1 (ranked)
- **training-5** [P1] Phase 1 spend is unverified (no billed figure for any run), and training alone (about $38.4) exceeds TRAIN_RESERVE $35 (`training/src/muselet_train/train.py`).
- **training-17** [P1] In the pilots, finance_review val accuracy is 0–25%; it's a demo-critical skill (`training/reports/phase1_pilot-lr4e-4.md`).
- **training-10** [P1] 4 catalog examples (the G1 generation seeds) are still exact eval items, and the HobbyLM TSV load is unasserted (`skills/catalog.json`, `training/src/muselet_train/decontam.py`).
- **training-8** [P1] No per-label 15% adjudication STOP gate, and the per-row A1 trigger is narrower than SPEC (`training/src/muselet_train/adjudicate.py`).
- **training-14** [P1] main has catalog v2 but the v1 parity samples, so the parity gate is off (`training/artifacts/route_render_samples.jsonl`).
- **training-15** [P1] The stratified teacher subset skews the label prior and mixes hard and soft targets (`training/src/muselet_train/teacher.py`).
- **training-11** [P1] Finder selection=yes can't happen at runtime, but constrain() now forces it for copy_selection (`training/src/muselet_train/contexts.py`).

Resolved this pass: training-3, training-6, training-7, training-16 (earlier: 1, 2, 4). Open P2: training-9, -12, -13, -18, -19, -20.

## Highest-leverage next moves
1. Before the main run, record the `tinker billing` figure and set --max-usd to 60 minus billed spend; raise TRAIN_RESERVE to at least $40 (training-5).
2. Inspect finance_review vs MULTI_STEP on v2all and run with --final-full-val (training-17).
3. Replace the 4 catalog examples that are eval items and assert the HobbyLM count (training-10).
4. Add the 15% A1 STOP and re-score the about 1.1K constrained-context rows with the teacher, about $0.6 (training-8, training-20).
5. Land the 41-option render artifact on main; save sampler weights at each eval and export the best-val step (training-14, training-18).
