# architect digest - pass 19 (2026-10-24T09:30Z)
Reviewed: main 2920225, wip/local 3e03686, cloud/data-pipeline 5371185, cloud/decisions 3a865a0, cloud/finance 529e9ff, cloud/finance-2 dfaf785, cloud/finance-3 31be399, cloud/fixtures-docs 4bf2291, cloud/bench f584cb2, cloud/advisor 9432c30, cloud/advisor-2 0a65f75, cloud/advisor-3 ca93147, cloud/pitch ad1b058, cloud/pitch-2 3303678, cloud/brain-2 741465c, cloud/brain-3 14a3f52, cloud/grounding 3441ee8.
New: cloud/decisions (Tinker System One backend; the choice_renderer refactor is behavior-preserving), cloud/pitch-2 (claims re-cited against main; confirmation scope stated honestly as partial), data-pipeline dedup --pin-split-from. main and wip/local are unchanged.

## Open P0/P1 (ranked)
1. architect-12 P1 - Phase-1 main LoRA trained on stale route data; it2 not reported - training/src/muselet_train/datums.py (cloud/data-pipeline)
2. architect-8 P1 - No router_check results (base vs LoRA, tau, MLX parity) - evals/router_check.py
3. architect-13 P1 - Cloud Tinker System One backend reports as 'muselet', untagged - bench/systemone/cli.py (cloud/decisions)
4. architect-10 P1 - Grounder unused at runtime; every click fails - ml/src/brain/orchestrator.py:785

## Highest-leverage next moves
1. Run router_check on base 0.8B/4B/9B and the current LoRA; commit the JSON. This gives a tuned-vs-tuned baseline and a fallback. ~30 min.
2. Finish it2 on the pinned val split; export; MLX parity on the Mac; ship the winner at its own tau. ~1.5 h.
3. Before merging cloud/decisions: stamp the backend into the model name and responses, and keep cloud numbers out of headline tables. ~15 min.
4. Wire Grounder into the click path (bench/grounding/README.md:90 shows the call). ~1 h.
5. Run planner_offline, then the four demo flows and the HobbyLM/DeskMind benches with --backend mlx only. ~3 h.
