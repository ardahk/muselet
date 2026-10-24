# architect digest - pass 18 (2026-10-24T09:20Z, full re-verify against main 2920225)
Reviewed: main 2920225, wip/local c85a000, cloud/data-pipeline 5371185, cloud/finance 529e9ff, cloud/finance-2 dfaf785, cloud/finance-3 31be399, cloud/fixtures-docs 4bf2291, cloud/bench f584cb2, cloud/advisor 9432c30, cloud/advisor-2 0a65f75, cloud/advisor-3 ca93147, cloud/pitch ad1b058, cloud/brain-2 741465c, cloud/brain-3 14a3f52, cloud/grounding 3441ee8.
Re-verified every open finding against main 2920225. New merges reviewed: split_model untied-head fix (5bc295d, tested), offline planner bench with runtime-equivalent grading (2920225; scenarios reject premature done and destructive rm), and the bench symlink/safety fixes. No new findings.

## Open P0/P1 (ranked)
1. architect-12 P1 - Phase-1 main LoRA trained on stale route data (confirmed); it2 not reported yet (branch-only: cloud/data-pipeline) - training/src/muselet_train/datums.py
2. architect-8 P1 - No router_check results (base vs LoRA, tau, MLX parity) committed; about 2.7 h to Sat 12:00 PDT - evals/router_check.py
3. architect-10 P1 - Grounder only used in bench/; runtime click always fails - ml/src/brain/orchestrator.py:785

## Highest-leverage next moves
1. Run evals/router_check.py on base 0.8B/4B (and 9B now that the head fix is in) plus the current main LoRA; commit the JSON. This gives a tuned-vs-tuned baseline and a fallback. ~30 min.
2. Finish it2 with the pinned val split; export; router_check parity on the Mac; ship the winner at its own tau, others selectable. ~1.5 h.
3. Wire Grounder into the click path: screenshot -> Grounder(capture=handskit_capture(server.rpc)) -> global x,y -> act with expect (bench/grounding/README.md:90 already shows the call). ~1 h.
4. Run planner_offline knob sweep, then the four demo flows through live_t1. ~2 h.
5. HobbyLM-125, DeskMind-13, JevBench and Typed Decisions on the merged bench harness. ~3 h.
