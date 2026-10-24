# training lane digest — pass 37 (main e56582b, cloud/data-pipeline f8b721a, cloud/decisions 43abfa3, cloud/comms 956d4ac, cloud/report-2 3c25e78)

Open: 0 P0, 11 P1, 14 P2. Nothing new or resolved. training-44 corrected: main parity is intact; the risk is it3 (catalog v3) vs main/comms router:false flags.

## Ranked open P0/P1
1. training-44 P1 — it3 catalog v3 routes compose_text + draft_email; main (compose_text) and comms (draft_email) mark them router:false; header parity only xfails on mismatch.
2. training-43 P1 — frozen route_v2 has 0.4% <=3-word items; it3 selection blind to short commands.
3. training-29 P1 — short_edit1 rule mostly false positives; hard gate; now also pre-filters the it3 pool (gate_filter) and thinned route_v2.
4. training-37 P1 — route_v1_clean length-skewed; no full/short number for it2.
5. training-5 P1 — shared Tinker cap; decisions + it3 runs both pending.
6. training-26 P1 — pronoun ARGS treated as concrete.
7. training-28 P1 — media_control contexts inside Premiere Pro.
8. training-24 P1 — ASK undercoverage.
9. training-25 P1 — weak labels media_control/dark_mode/find_file.
10. training-8 / training-15 P1 — no adjudication STOP gate; teacher subset skew.

## Next moves
1. Decide the it3 catalog; land it on main with matching router flags, new parity samples and the it3 router together.
2. Add a short-command stratum to route_v2 (or report by length) before it3 selection.
3. Narrow short_edit1.
4. One shared Tinker ledger before decisions and it3 runs.
5. Judge decisions H6 on route_val/route_v2.
