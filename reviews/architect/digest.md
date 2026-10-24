# architect digest - pass 31 (2026-10-24T12:28Z)
Reviewed: main fbd5aa0, wip/local 2f26223, cloud/data-pipeline 735686f, cloud/decisions 6d395df, cloud/finance 529e9ff, cloud/finance-2 dfaf785, cloud/finance-3 31be399, cloud/fixtures-docs 4bf2291, cloud/bench f584cb2, cloud/advisor 9432c30, cloud/advisor-2 0a65f75, cloud/advisor-3 ca93147, cloud/pitch ad1b058, cloud/pitch-2 3303678, cloud/pitch-3 e203181, cloud/pitch-4 6393857, cloud/brain-2 741465c, cloud/brain-3 14a3f52, cloud/brain-4 dfb66a3, cloud/brain-5 b752261, cloud/hobby-gaps 156556e, cloud/grounding 3441ee8, cloud/grounder-wire afb12a6.
New: as-trained it2 overlap re-check (sealed-r4 0/125; DeskMind hits are CJK normalizer artifacts); AGENTS.md restricts competitor benches to it2 or later; pitch-4 contamination disclosures. architect-19 resolved; architect-20 (P2) filed.

## Open P0/P1 (ranked)
1. architect-8 P1 - No Mac parity result; Tinker .961 vs MLX .913 on clean 103 unexplained - evals/router_check.py
2. architect-13 P1 - Cloud Tinker System One backend reports as 'muselet' - bench/systemone/cli.py:42
(P2: architect-20 Chinese DeskMind goals vs English-only router; architect-15 delta/view outside catalog; architect-16 no timer cancel/list skill)

## Highest-leverage next moves
1. Run the it2 Mac parity check and commit the router_check JSON (explain .961 vs .913). ~20 min.
2. Score the 13 DeskMind diag goals offline with it2 before the morning live run. ~15 min.
3. Label the System One backend in outputs and results. ~15 min.
4. Catalog delta/view and refresh the parity reference. ~30 min.
5. cancel_timer/list_timers skills. ~30 min.
