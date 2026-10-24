# training review digest: pass 15
_heads: cloud/data-pipeline a6b229a (main run report + parity_300 + route_items file fix); main 280715d, wip/local 38768f3, other cloud/* unchanged_

## Open P0/P1 (ranked)
- **training-23** [P0] The main run was trained and evaluated on the stale pre-fix route_dedup.jsonl; contexts are unconstrained, and G3 and external-eval contamination are unverified (`training/src/muselet_train/datums.py:57@43ea71a`).
- **training-24** [P1] The router almost never ASKs: 194 train items, val 0/3 (`training/reports/phase1_main.md`).
- **training-25** [P1] Main run per-label accuracy: media_control 32%, dark_mode 68%, find_file 71% (`training/reports/phase1_main.md`).
- **training-5** [P1] No billed spend is recorded; the billing guard lags and --max-usd is per-run only, and a retrain adds about $29 (`tools/tinker_spend.py`, `train.py`).
- **training-14** [P1] main has catalog v2 but 36-option parity samples, so the parity test xfails while the pitch claims parity (`training/artifacts/route_render_samples.jsonl`).
- **training-8** [P1] No per-label 15% A1 STOP gate (`training/src/muselet_train/adjudicate.py`).
- **training-15** [P1] The stratified teacher subset skews the label prior (`training/src/muselet_train/teacher.py`).
- **training-11** [P1] Finder selection=yes can't happen at runtime, but it's forced for copy_selection (`training/src/muselet_train/contexts.py`).

Resolved this pass: training-17 (finance_review val 1.000, n=36). Open P2: training-9, -10, -12, -13, -18, -19, -20, -22.

## Highest-leverage next moves
1. Don't export or quote `main`. Grep the external utterances and G3 rows in /data/gen/v2all/route_dedup.jsonl, then retrain from route_train/route_val at a6b229a (about $29) (training-23).
2. Before that retrain, read the billed spend and set --max-usd to at most 150 minus billed minus unbilled estimates (training-5).
3. Raise surviving ASK coverage to about 2% of route items before the retrain (training-24).
4. After the retrain, read pred_val for media_control, dark_mode and find_file and add contrast pairs (training-25); regenerate parity_300 from the new checkpoint with --teacher-files (training-22).
5. Land the 41-option render artifact on main (training-14).
