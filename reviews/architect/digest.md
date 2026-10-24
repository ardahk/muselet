# architect digest - pass 25 (2026-10-24T10:55Z)
Reviewed: main 26ff05b, wip/local 2c79363, cloud/data-pipeline eae3b7e, cloud/decisions 91a62c2, cloud/finance 529e9ff, cloud/finance-2 dfaf785, cloud/finance-3 31be399, cloud/fixtures-docs 4bf2291, cloud/bench f584cb2, cloud/advisor 9432c30, cloud/advisor-2 0a65f75, cloud/advisor-3 ca93147, cloud/pitch ad1b058, cloud/pitch-2 3303678, cloud/brain-2 741465c, cloud/brain-3 14a3f52, cloud/brain-4 dfb66a3, cloud/brain-5 b752261, cloud/hobby-gaps 861b991, cloud/grounding 3441ee8.
New: main merged brain-5 (+ argfix kill/cut/shut down = off) and refreshed the catalog-v2 route parity reference; it2 adds the H9 runtime ARGS gate; decisions adds a reasoning-teacher gate (pilot spend $5.84 non-Tinker); hobby-gaps merged main but still conflicts (3 hunks).

## Open P0/P1 (ranked)
1. architect-17 P1 - serve_brain.sh defaults to a pre-untie-fix, stale-data router that loses e2e (.702 vs .716) - tools/serve_brain.sh
2. architect-12 P1 - Main LoRA trained on stale route data; it2 relaunching with the H9 gate - training/ (cloud/data-pipeline)
3. architect-8 P1 - No committed router_check JSON or exported-weights parity - evals/router_check.py
4. architect-10 P1 - Grounder unused at runtime - ml/src/brain/orchestrator.py:785
5. architect-13 P1 - Cloud Tinker System One backend reports as 'muselet' - bench/systemone/cli.py:42 (cloud/decisions)
(P2: architect-15 delta/view outside catalog, now on main; architect-16 no timer cancel/list skill)

## Highest-leverage next moves
1. Re-export main-final with `export untie` (merge f39efe4), parity, rerun the router_check 2x2; default to the e2e winner. ~45 min.
2. Land it2 gated on H9 plus route on the pinned val; export with untie. ~1.5 h.
3. Merge hobby-gaps (resolve 3 hunks), then add delta/view to the catalog and refresh the parity reference once. ~40 min.
4. Assign Grounder click wiring. ~1 h.
5. Add cancel_timer/list_timers skills. ~30 min.
