# architect digest - pass 20 (2026-10-24T09:45Z)
Reviewed: main 28dc259, wip/local e1701a3, cloud/data-pipeline 80cb13f, cloud/decisions 3a865a0, cloud/finance 529e9ff, cloud/finance-2 dfaf785, cloud/finance-3 31be399, cloud/fixtures-docs 4bf2291, cloud/bench f584cb2, cloud/advisor 9432c30, cloud/advisor-2 0a65f75, cloud/advisor-3 ca93147, cloud/pitch ad1b058, cloud/pitch-2 3303678, cloud/brain-2 741465c, cloud/brain-3 14a3f52, cloud/brain-4 3aca368, cloud/hobby-gaps 14ff59b, cloud/grounding 3441ee8.
New: main 28dc259 (planner holdout; router_check ARGS e2e), cloud/brain-4 (split ROUTE and ARGS models, defaulting to shared weights; planner knobs as flags; looks correct, 1 textual conflict with hobby-gaps in orchestrator.py), cloud/hobby-gaps (calculator and relative controls; see architect-14), data-pipeline (runtime-rendered ARGS EM, tighter decontamination).

## Open P0/P1 (ranked)
1. architect-14 P1 (P0 on merge) - Calculator pre-router hijacks ranges/fractions - ml/src/brain/orchestrator.py:296 (cloud/hobby-gaps)
2. architect-12 P1 - Main LoRA trained on stale route data with non-runtime ARGS rendering; it2 pending - training/src/muselet_train/datums.py
3. architect-8 P1 - No router_check results (base vs LoRA, tau, ARGS e2e, MLX parity) - evals/router_check.py
4. architect-13 P1 - Cloud Tinker System One backend reports as 'muselet' - bench/systemone/cli.py (cloud/decisions)
5. architect-10 P1 - Grounder unused at runtime - ml/src/brain/orchestrator.py:785

## Highest-leverage next moves
1. Gate hobby-gaps' calc short-circuit to pure math questions (or route first, calc on ANSWER) before merging; add the 8 negative cases. ~20 min.
2. Run router_check (route + ARGS e2e) on base 0.8B/4B/9B and the current LoRA; commit the JSON. ~30 min.
3. Finish it2 and gate on 'ARGS EM runtime', not the old ARGS EM; export; MLX parity on the Mac. ~1.5 h.
4. Wire Grounder into the click path. ~1 h.
5. Run planner_offline including the holdout, then the demo flows and the MLX-only benches. ~3 h.
