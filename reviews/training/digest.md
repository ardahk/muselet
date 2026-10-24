# training lane digest — pass 44 (main 3876f3a, wip/local 3cfa06d, cloud/comms-2 c65ee70)

Open: 0 P0, 11 P1, 15 P2. Correction: training-5 downgraded P1 -> P2. An account-wide Tinker spend guard has existed since 085b0c8 (tools/tinker_spend.py: pause at $120, stop at $140, polled every 15 min). Remaining gaps: billing lags by hours, the stop message goes to one session, and the docs still say $60/$135. No other lane changes; the hobbylm replay Path fix may unblock the pending HobbyLM sealed-r4 results.

## Ranked open P0/P1
1. training-44 P1 — it3 depends on catalog v3 (43 options: draft_email + compose_text routable); main runtime is v2 with both router:false; parity test xfails on mismatch.
2. training-45 P1 — it3 ARGS: 15.7% audit noise fixed only on the 1,061 sampled rows; 'a lot' = 25 in training vs 30 in brain-8 runtime.
3. training-29 P1 — short_edit1: 143 of 156 data-route gate drops ('text her' vs 'email her'); hard gate; also 24 of 44 planner-demo drops.
4. training-43 P1 — route_v2 has 0.4% <=3-word items; it3 selection (incl. new tau precision rule) blind to short commands.
5. training-37 P1 — route_v1_clean length-skewed; no full/short number for it2.
6. training-8 / training-15 P1 — adjudicator sees gold; no per-label stop gate.
7. training-24 P1 — ASK undercoverage (it3cand 451 -> 834, pending training).
8. training-25 P1 — weak labels (re-judged in it3cand, pending training).
9. training-26 P1 — pronoun ARGS treated as concrete.
10. training-28 P1 — media_control contexts inside Premiere Pro.

## Next moves
1. Ship it3 only with main on catalog v3 (both skills routable) + v3 parity samples, and make a parity mismatch fail instead of xfail.
2. Re-audit 500 it3 ARGS rows; align 'a lot' with brain-8 (30).
3. Narrow short_edit1 and restore the dropped short commands.
4. Add a short-command stratum to route_v2 or report router accuracy by length.
5. Confirm the decisions/it3 sessions receive the spend-guard stop message, leave pre-run headroom for the billing lag, and fix the $60/$135 docs.
