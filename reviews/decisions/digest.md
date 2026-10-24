# decisions — digest (pass 29)

Heads: main 27ebd13 (HANDOFF.md merged), cloud/decisions b78d778 (FULL run dec-full-lr2e4 trained, 347 steps; no report), data-pipeline 34aff30, planner-retrieval 9786fa4 (v2-tune gold is the default bank, decisions-29 P2).

## Open P0/P1
1. decisions-26 P1 LR pilot + FULL run (dec-full-lr2e4) with no hypothesis, data revision, cost or metrics committed — reports/checkpoints.jsonl
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
