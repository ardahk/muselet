# architect digest - pass 22 (2026-10-24T10:12Z)
Reviewed: main 758a017, wip/local 630d661, cloud/data-pipeline 80cb13f, cloud/decisions c08a96d, cloud/finance 529e9ff, cloud/finance-2 dfaf785, cloud/finance-3 31be399, cloud/fixtures-docs 4bf2291, cloud/bench f584cb2, cloud/advisor 9432c30, cloud/advisor-2 0a65f75, cloud/advisor-3 ca93147, cloud/pitch ad1b058, cloud/pitch-2 3303678, cloud/brain-2 741465c, cloud/brain-3 14a3f52, cloud/brain-4 dfb66a3, cloud/brain-5 003d1bb, cloud/hobby-gaps 929b931, cloud/grounding 3441ee8.
New: cloud/brain-5 (vague deltas, polarity lexicon with negation->ASK, compound follow-ups/compound_to_planner, fuzzy path resolve with symlinks not followed, ratio>=0.88, ASK on several matches, view arg with cmd+N fallback); cloud/decisions generic decisions pipeline (decontam set looks complete for Typed Decisions/JevBench); wip/local HandsKit delta/view/timers/no_text_target work.

## Open P0/P1 (ranked)
1. architect-12 P1 - Main LoRA trained on stale route data and non-runtime ARGS; it2 pending - training/src/muselet_train/datums.py (cloud/data-pipeline)
2. architect-8 P1 - No router_check results (base vs LoRA, tau, ARGS e2e, MLX parity) - evals/router_check.py
3. architect-13 P1 - Cloud Tinker System One backend reports as 'muselet' - bench/systemone/cli.py:42 (cloud/decisions)
4. architect-10 P1 - Grounder unused at runtime; no builder assigned - ml/src/brain/orchestrator.py:785
(P2: architect-15 brain-5 delta/view outside catalog, duplicated with hobby-gaps)

## Highest-leverage next moves
1. Run router_check (route + ARGS e2e) on base and current LoRA; commit the JSON. ~30 min.
2. Finish it2 gated on 'ARGS EM runtime'; export; MLX parity. ~1.5 h.
3. Merge order: hobby-gaps -> brain-5 (rebased onto catalog delta/view) -> brain-4. ~30 min.
4. Assign Grounder click wiring. ~1 h.
5. Stamp the backend into the systemone model name. ~15 min.
