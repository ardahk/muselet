# architect digest - pass 29 (2026-10-24T11:57Z)
Reviewed: main 04c3930, wip/local aec8fbf, cloud/data-pipeline 9b36081, cloud/decisions 6d395df, cloud/finance 529e9ff, cloud/finance-2 dfaf785, cloud/finance-3 31be399, cloud/fixtures-docs 4bf2291, cloud/bench f584cb2, cloud/advisor 9432c30, cloud/advisor-2 0a65f75, cloud/advisor-3 ca93147, cloud/pitch ad1b058, cloud/pitch-2 3303678, cloud/pitch-3 e203181, cloud/brain-2 741465c, cloud/brain-3 14a3f52, cloud/brain-4 dfb66a3, cloud/brain-5 b752261, cloud/hobby-gaps 156556e, cloud/grounding 3441ee8, cloud/grounder-wire afb12a6.
New: main merged grounder-wire, pitch-3 and planner rules 16-18; route_v1_clean_both (103 cases) added. architect-10 resolved.

## Open P0/P1 (ranked)
1. architect-18 P1 - serve_brain.sh quotes full-route_v1 numbers; router_check defaults to the contaminated set - tools/serve_brain.sh
2. architect-12 P1 - Shipped r2 trained on stale data; it2 fails the gate, it2b pending - training/ (cloud/data-pipeline)
3. architect-8 P1 - No committed router_check or parity JSON - evals/router_check.py
4. architect-13 P1 - Cloud Tinker System One backend reports as 'muselet' - bench/systemone/cli.py:42
(P2: architect-15 delta/view outside catalog; architect-16 no timer cancel/list skill)

## Highest-leverage next moves
1. Commit clean_both router_check JSON for base/r2; switch router_check's default to the clean set; fix the serve_brain.sh header. ~15 min.
2. Train it2b; compare with r2 on route_v1_clean_both; ship the winner. ~1.5 h.
3. Live-test click "<target>" on a Premiere panel (latency and accuracy of eyes-4b). ~30 min.
4. Catalog delta/view and refresh the parity reference. ~30 min.
5. cancel_timer/list_timers skills. ~30 min.
