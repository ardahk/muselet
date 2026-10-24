# architect digest - pass 27 (2026-10-24T11:24Z)
Reviewed: main d502b78, wip/local 0db1681, cloud/data-pipeline 0c1ca3d, cloud/decisions 6d395df, cloud/finance 529e9ff, cloud/finance-2 dfaf785, cloud/finance-3 31be399, cloud/fixtures-docs 4bf2291, cloud/bench f584cb2, cloud/advisor 9432c30, cloud/advisor-2 0a65f75, cloud/advisor-3 ca93147, cloud/pitch ad1b058, cloud/pitch-2 3303678, cloud/brain-2 741465c, cloud/brain-3 14a3f52, cloud/brain-4 dfb66a3, cloud/brain-5 b752261, cloud/hobby-gaps 156556e, cloud/grounding 3441ee8.
New: data-pipeline gates it2b against route_v1/live_t1/external (9 train items dropped, val/args clean); wip/local moves MLX work in generic_decide to one worker thread (fixes the shim's thread-local stream crash; looks correct). main unchanged.

## Open P0/P1 (ranked)
1. architect-18 P1 (P0 if published) - Full-route_v1 trained-router scores inflated (37/140 contaminated); no clean-subset results - tools/serve_brain.sh, evals/router_check.py
2. architect-12 P1 - Main LoRA trained on stale route data; it2b clean, result pending - training/ (cloud/data-pipeline)
3. architect-8 P1 - No committed router_check JSON or r2 parity record - evals/router_check.py
4. architect-10 P1 - Grounder unused at runtime - ml/src/brain/orchestrator.py:785
5. architect-13 P1 - Cloud Tinker System One backend reports as 'muselet' - bench/systemone/cli.py:42
(P2: architect-15 delta/view outside catalog; architect-16 no timer cancel/list skill)

## Highest-leverage next moves
1. router_check on route_v1_clean for base, r1, r2 (route + ARGS e2e); commit the JSON; update serve_brain/pitch. ~30 min.
2. Train it2b; compare to r2 on the pinned val and route_v1_clean. ~1.5 h.
3. Assign Grounder click wiring. ~1 h.
4. Catalog delta/view and refresh the parity reference. ~30 min.
5. cancel_timer/list_timers skills. ~30 min.
