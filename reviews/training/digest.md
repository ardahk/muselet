# training lane digest — pass 41 (main 026aff0, cloud/brain-8 4546d09, cloud/planner-demos 84798ec)

Open: 0 P0, 12 P1, 15 P2. New: training-46 (P2). main merged data-route and report-2; training-44 now has both sides on main.

## Ranked open P0/P1
1. training-44 P1 — it3cand trains draft_email (330) + compose_text (127) as routable; main marks both router:false (comms merged).
2. training-45 P1 — it3cand ARGS: 15.7% audit noise fixed only on the 1,061 sampled rows; ~29k rows get deterministic rules only.
3. training-29 P1 — short_edit1: 143 of 156 data-route gate drops ('text her' vs 'email her'); hard gate.
4. training-43 P1 — route_v2 has 0.4% <=3-word items; it3 selection blind to short commands.
5. training-37 P1 — route_v1_clean length-skewed; no full/short number for it2.
6. training-5 P1 — shared Tinker cap; decisions pilots ran, it3 pending.
7. training-8 / training-15 P1 — adjudicator sees gold; no per-label stop gate.
8. training-24 P1 — ASK undercoverage (it3cand 451 -> 834, pending training).
9. training-25 P1 — weak labels (re-judged in it3cand, pending training).
10. training-26 P1 — pronoun ARGS treated as concrete (no change in data-route).
11. training-28 P1 — media_control contexts inside Premiere Pro (partly via media group).

## Next moves
1. Settle the it3 catalog: either make draft_email/compose_text routable on main or drop them from it3cand before training.
2. Re-audit 500 it3cand ARGS rows; full-pool ARGS re-judge for high-noise skills if residual > 8%.
3. Narrow short_edit1 and restore the 137 dropped generated rows.
4. Add a short-command stratum to route_v2 or report it by length.
5. One shared Tinker ledger (record decisions pilot spend) before it3.
