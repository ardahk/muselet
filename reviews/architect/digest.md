# architect digest - pass 37 (2026-10-24T16:40Z)
Reviewed: main c949565, wip/local 4ec066f, cloud/app-ui afb2688, cloud/brain-7 13432fe, cloud/native-research fa88c22, cloud/report dffa733, cloud/data-pipeline 6c1e565, cloud/decisions 184c80f, cloud/finance 529e9ff, cloud/finance-2 dfaf785, cloud/finance-3 31be399, cloud/fixtures-docs 4bf2291, cloud/bench f584cb2, cloud/advisor 9432c30, cloud/advisor-2 0a65f75, cloud/advisor-3 ca93147, cloud/pitch ad1b058, cloud/pitch-2 3303678, cloud/pitch-3 e203181, cloud/pitch-4 6393857, cloud/brain-2 741465c, cloud/brain-3 14a3f52, cloud/brain-4 dfb66a3, cloud/brain-5 b752261, cloud/brain-6 780f49d, cloud/hobby-gaps 156556e, cloud/grounding 3441ee8, cloud/grounder-wire afb12a6.
New: cloud/app-ui (pet mascot, panel, Settings, config frame), cloud/brain-7 (first-use fixes, compose_text, config handler), cloud/data-pipeline it3 prep (route_v2 955 items with 0 overlap, catalog v3), cloud/decisions trainer and calibration, cloud/report REPORT.md (quotes only clean and it2-only numbers, consistent with AGENTS.md), cloud/native-research doc. architect-21 superseded by 22 and 23.

## Open P0/P1 (ranked)
1. architect-8 P1 - No Mac parity result; Tinker .961 vs MLX .913 on clean 103 unexplained - evals/router_check.py
2. architect-13 P1 - Cloud Tinker System One backend reports as 'muselet' - bench/systemone/cli.py:42
(P2: architect-23 catalog v3 lacks timer, delta/view and draft-send skills and router flags; architect-22 config_ack shape mismatch app-ui vs brain-7; architect-20 Chinese DeskMind goals vs English-only router; architect-15 delta/view; architect-16 timer cancel/list)

## Highest-leverage next moves
1. Before it3 generation, add cancel_timer, list_timers, set_brightness.delta, open_folder.view and send_draft to catalog v3, carry over router:false, and regenerate the parity reference (closes 15, 16, 23). ~45 min.
2. Merge one config handler (brain-7's) with 'ok' in the ack; drop app-ui's server.py and protocol.py changes. ~15 min.
3. Run the it2 Mac parity check and commit the router_check JSON. ~20 min.
4. Score the 13 DeskMind diag goals offline with it2. ~15 min.
5. Label the System One backend in outputs. ~15 min.
