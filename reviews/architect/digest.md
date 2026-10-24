# architect digest - pass 21 (2026-10-24T09:58Z)
Reviewed: main 758a017, wip/local a3f82f1, cloud/data-pipeline 80cb13f, cloud/decisions 3a865a0, cloud/finance 529e9ff, cloud/finance-2 dfaf785, cloud/finance-3 31be399, cloud/fixtures-docs 4bf2291, cloud/bench f584cb2, cloud/advisor 9432c30, cloud/advisor-2 0a65f75, cloud/advisor-3 ca93147, cloud/pitch ad1b058, cloud/pitch-2 3303678, cloud/brain-2 741465c, cloud/brain-3 14a3f52, cloud/brain-4 dfb66a3, cloud/hobby-gaps 929b931, cloud/grounding 3441ee8.
New: hobby-gaps fixed the calculator hijack (architect-14 resolved). brain-4 adds an opt-in --planner-escalate-model at the loop guard and changes the default planner history from 'marked' to 'dsl' (a knob change; record the hypothesis and planner_offline delta per the standing rule). main adds the brain-5 brief (vague deltas, polarity lexicon, compound follow-ups, fuzzy trash path behind confirm with the full path shown, view arg); its design is consistent with the safety rules.

## Open P0/P1 (ranked)
1. architect-12 P1 - Main LoRA trained on stale route data and non-runtime ARGS rendering; it2 pending - training/src/muselet_train/datums.py (cloud/data-pipeline)
2. architect-8 P1 - No router_check results (base vs LoRA, tau, ARGS e2e, MLX parity) - evals/router_check.py
3. architect-13 P1 - Cloud Tinker System One backend reports as 'muselet' - bench/systemone/cli.py:42 (cloud/decisions)
4. architect-10 P1 - Grounder unused at runtime; no builder assigned - ml/src/brain/orchestrator.py:785

## Highest-leverage next moves
1. Run router_check (route + ARGS e2e) on base 0.8B/4B/9B and the current LoRA; commit the JSON. ~30 min.
2. Finish it2 gated on 'ARGS EM runtime'; export; MLX parity on the Mac. ~1.5 h.
3. Assign Grounder click wiring to a builder (brain-5 doesn't cover it; it doesn't touch brain-5's area). ~1 h.
4. Stamp the backend into the systemone model name before cloud/decisions merges. ~15 min.
5. Run planner_offline holdout for brain-4's 'dsl' history default vs 'marked' before merging. ~20 min.
