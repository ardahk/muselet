# architect digest - pass 28 (2026-10-24T11:42Z)
Reviewed: main 7147694, wip/local 5764a0d, cloud/data-pipeline 9b36081, cloud/decisions 6d395df, cloud/finance 529e9ff, cloud/finance-2 dfaf785, cloud/finance-3 31be399, cloud/fixtures-docs 4bf2291, cloud/bench f584cb2, cloud/advisor 9432c30, cloud/advisor-2 0a65f75, cloud/advisor-3 ca93147, cloud/pitch ad1b058, cloud/pitch-2 3303678, cloud/pitch-3 e203181, cloud/brain-2 741465c, cloud/brain-3 14a3f52, cloud/brain-4 dfb66a3, cloud/brain-5 b752261, cloud/hobby-gaps 156556e, cloud/grounding 3441ee8, cloud/grounder-wire afb12a6.
New: cloud/grounder-wire wires the Grounder into the planner (click "<target>"); it2 report (strong, but fails the contamination gate, so not a candidate); pitch-3 fills clean-subset router numbers; main adds planner holdout-2 and the generic_decide MLX worker thread.

## Open P0/P1 (ranked)
1. architect-18 P1 - Full-route_v1 numbers still quoted in serve_brain.sh; router_check defaults to the contaminated set - tools/serve_brain.sh
2. architect-12 P1 - Shipped r2 trained on stale data; it2 fails the gate, it2b pending - training/ (cloud/data-pipeline)
3. architect-10 P1 - Grounder wired on cloud/grounder-wire, not merged - ml/src/brain/orchestrator.py:785
4. architect-8 P1 - No committed router_check or parity JSON - evals/router_check.py
5. architect-13 P1 - Cloud Tinker System One backend reports as 'muselet' - bench/systemone/cli.py:42
(P2: architect-15 delta/view outside catalog; architect-16 no timer cancel/list skill)

## Highest-leverage next moves
1. Merge cloud/grounder-wire after checking that grounded clicks pass the risk/confirm gate. ~30 min.
2. Train it2b and compare with r2 on route_v1_clean and the pinned val; ship the winner. ~1.5 h.
3. Commit runs/router/*_clean.json, switch router_check's default to the clean set, and update the serve_brain.sh header. ~15 min.
4. Catalog delta/view and refresh the parity reference. ~30 min.
5. cancel_timer/list_timers skills. ~30 min.
