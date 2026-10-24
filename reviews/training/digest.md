# training lane digest — pass 36 (cloud/data-pipeline 6c1e565, cloud/decisions 184c80f, cloud/brain-7 13432fe, cloud/report dffa733, main c949565)

Open: 0 P0, 11 P1, 14 P2. Resolved training-41 (code families restored, 15,167 decisions) and training-32 (30% replay from it2b). New: training-43, training-44 (P1).

## Ranked open P0/P1
1. training-44 P1 — router option set diverges: brain-7 (compose_text router:false, v2) vs it3 catalog_v3 (compose_text + draft_email routable) vs main training catalog.py (no router filter).
2. training-43 P1 — frozen route_v2 has 0.4% <=3-word items; it3 selection blind to short commands.
3. training-29 P1 — short_edit1 rule mostly false positives; hard gate; also thins route_v2.
4. training-37 P1 — route_v1_clean length-skewed; no full/short number for it2.
5. training-5 P1 — shared Tinker cap; decisions + it3 runs both pending.
6. training-26 P1 — pronoun ARGS treated as concrete.
7. training-28 P1 — media_control contexts inside Premiere Pro.
8. training-24 P1 — ASK undercoverage.
9. training-25 P1 — weak labels media_control/dark_mode/find_file.
10. training-8 / training-15 P1 — no adjudication STOP gate; teacher subset skew.

## Next moves
1. Decide the it3 catalog (v3) and land it with router filter + parity samples on main before brain-7 merges.
2. Add a short-command stratum to route_v2 (or report by length) before it3 selection.
3. Narrow short_edit1.
4. One shared Tinker ledger before decisions and it3 runs.
5. Judge decisions H6 on route_val/route_v2.
