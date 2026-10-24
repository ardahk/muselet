# architect digest - pass 26 (2026-10-24T11:12Z)
Reviewed: main d502b78, wip/local c7c04ce, cloud/data-pipeline 19737e1, cloud/decisions 6d395df, cloud/finance 529e9ff, cloud/finance-2 dfaf785, cloud/finance-3 31be399, cloud/fixtures-docs 4bf2291, cloud/bench f584cb2, cloud/advisor 9432c30, cloud/advisor-2 0a65f75, cloud/advisor-3 ca93147, cloud/pitch ad1b058, cloud/pitch-2 3303678, cloud/brain-2 741465c, cloud/brain-3 14a3f52, cloud/brain-4 dfb66a3, cloud/brain-5 b752261, cloud/hobby-gaps 156556e, cloud/grounding 3441ee8.
New: main merged hobby-gaps, defaulted serve_brain to the fixed r2 router (architect-17 resolved), and added route_v1_clean; data-pipeline added a hard eval-contamination gate; decisions amendment 3.

## Open P0/P1 (ranked)
1. architect-18 P1 (P0 if published) - route_v1 contaminated for trained routers (37/140); full-set scores inflated - tools/serve_brain.sh, evals/route_v1_clean.jsonl
2. architect-12 P1 - Main LoRA trained on stale route data; it2 pending (8 route_v1 pairs left) - training/ (cloud/data-pipeline)
3. architect-8 P1 - No committed router_check JSON or r2 parity record - evals/router_check.py
4. architect-10 P1 - Grounder unused at runtime - ml/src/brain/orchestrator.py:785
5. architect-13 P1 - Cloud Tinker System One backend reports as 'muselet' - bench/systemone/cli.py:42
(P2: architect-15 delta/view outside catalog; architect-16 no timer cancel/list skill)

## Highest-leverage next moves
1. Rerun router_check on route_v1_clean for base, r1 and r2 (route + ARGS e2e); commit the JSON; replace serve_brain/pitch numbers. ~30 min.
2. Clear it2's 8 route_v1 pairs through the hard gate, then relaunch. ~10 min.
3. Assign Grounder click wiring. ~1 h.
4. Add delta/view to the catalog and refresh the parity reference; drop _CODE_ARGS. ~30 min.
5. Add cancel_timer/list_timers skills. ~30 min.
