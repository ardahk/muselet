# architect digest - pass 30 (2026-10-24T12:12Z)
Reviewed: main d7c192f, wip/local 367d450, cloud/data-pipeline 0ce9ea6, cloud/decisions 6d395df, cloud/finance 529e9ff, cloud/finance-2 dfaf785, cloud/finance-3 31be399, cloud/fixtures-docs 4bf2291, cloud/bench f584cb2, cloud/advisor 9432c30, cloud/advisor-2 0a65f75, cloud/advisor-3 ca93147, cloud/pitch ad1b058, cloud/pitch-2 3303678, cloud/pitch-3 e203181, cloud/brain-2 741465c, cloud/brain-3 14a3f52, cloud/brain-4 dfb66a3, cloud/brain-5 b752261, cloud/hobby-gaps 156556e, cloud/grounding 3441ee8, cloud/grounder-wire afb12a6.
New: main defaults to it2 (clean route_v1 .913 vs r2 .864); AGENTS.md documents the serving config; data-pipeline adds the it2 untied export, a parity file and clean_subsets.json. architect-18 and architect-12 resolved; architect-19 filed.

## Open P0/P1 (ranked)
1. architect-19 P1 - Default it2 trained on near-copies of 16/64 DeskMind dyn tasks (+ sealed-r2/r3) - tools/serve_brain.sh
2. architect-8 P1 - No Mac parity result; Tinker .961 vs MLX .913 on clean 103 unexplained - evals/router_check.py
3. architect-13 P1 - Cloud Tinker System One backend reports as 'muselet' - bench/systemone/cli.py:42
(P2: architect-15 delta/view outside catalog; architect-16 no timer cancel/list skill)

## Highest-leverage next moves
1. Build per-set clean subsets for DeskMind dyn/diag and HobbyLM sealed; quote only those for it2/r2. ~20 min.
2. Train it2b (clean on every set) and compare to it2 on clean 103 + val. ~1.5 h.
3. Run the it2 Mac parity check against parity_300_it2.jsonl; commit the router_check JSON. ~20 min.
4. Label the System One backend in outputs. ~15 min.
5. Catalog delta/view + cancel_timer/list_timers. ~1 h.
