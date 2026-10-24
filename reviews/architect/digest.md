# architect digest - pass 17 (2026-10-24T09:08Z)
Reviewed: main bb494af, wip/local c85a000, cloud/data-pipeline 70b7d1b, cloud/finance 529e9ff, cloud/finance-2 dfaf785, cloud/finance-3 31be399, cloud/fixtures-docs 4bf2291, cloud/bench f584cb2, cloud/advisor 9432c30, cloud/advisor-2 0a65f75, cloud/advisor-3 ca93147, cloud/pitch ad1b058, cloud/brain-2 741465c, cloud/brain-3 14a3f52, cloud/grounding 3441ee8.
main merged cloud/brain-3 (resolves architect-11) and added evals/router_check.py (parity, dev-fitted tau, route_v1 per model) plus an offline planner benchmark (28 scenarios). cloud/data-pipeline confirmed the main run used stale data and started iteration 2. cloud/bench normalizes Typed Decisions answers and runs JevBench in the ml venv.

## Open P0/P1 (ranked)
1. architect-12 P1 - Main LoRA trained on stale route_dedup.jsonl (confirmed); it2 retrain in progress - training/src/muselet_train/datums.py
2. architect-8 P1 - Phase-1: router_check exists but has no results yet (base vs LoRA, MLX parity); about 3 h to Sat 12:00 PDT - evals/router_check.py
3. architect-10 P1 - Grounder merged but unused; every pixel click fails - ml/src/brain/orchestrator.py:785

## Highest-leverage next moves
1. Run router_check now on the base 4B/0.8B and the current main LoRA, so there is a tuned-vs-tuned baseline and a fallback whatever it2 delivers. ~30 min.
2. Finish it2 with the fixed reader; export; router_check parity on the Mac; ship whichever router wins at its own tau, with the others selectable by flag. ~1.5 h.
3. Wire the Grounder into the click path (architect-10). ~1 h.
4. Run the offline planner benchmark's knob sweep, then the four demo flows through live_t1. ~2 h.
5. HobbyLM-125, DeskMind-13, JevBench and Typed Decisions on cloud/bench. ~3 h.
