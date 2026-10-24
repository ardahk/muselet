# decisions — digest (pass 27)

Heads: main 026aff0 (report-2, data-route, data-planner merged: live_t1 19/22 now on main), brain-8 4546d09 (live_t1-derived fixes), planner-demos 84798ec (no eval gate on demo states, decisions-28 P2), cloud/decisions 694c198.

## Open P0/P1
1. decisions-26 P1 LR pilot (2 Tinker runs) with no hypothesis, data revision, cost or metrics committed — reports/checkpoints.jsonl
2. decisions-14 P1 live_t1 T1 19/22 quoted while live_t1 was the brain-5 tuning set — pitch/claims.md:17,67
3. decisions-25 P1 data-decisions brief targets a code-gold gap already closed — cloud/builder_data_decisions.md:8-9
4. decisions-17 P1 noul 37.6% true; score levels 4-5 = 1.9% of score gold
5. decisions-13 P1 route_acc still r2 .864 'top-1' — pitch/claims.md:13
6. decisions-4 / -3 / -5 P1 noul order flip; route regression runner; backend parity

## Highest-leverage next moves
- Commit lr_pilot.md (data rev, USD, dev/route_val per checkpoint) before the main decisions run (decisions-26).
- Label live_t1 a dev suite or freeze a held-out live set (decisions-14).
- Re-scope builder_data_decisions.md from full_gen.md@184c80f (decisions-25).
- Rebalance noul/score labels before the main decisions run (decisions-17); claims.md:13 to it2 (decisions-13).
