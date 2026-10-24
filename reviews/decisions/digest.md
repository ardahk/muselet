# decisions — digest (pass 23)

Heads: main cf53292 (merged report, brain-7, native-research; 3 data briefs), cloud/decisions 43abfa3 (lazy MLX imports), data-pipeline f8b721a (it3 gate-filter), comms 956d4ac (draft_email router:false, so the router option list is unchanged), report-2 3c25e78 (live_t1 results, raised gen cap to $120).

## Open P0/P1
1. decisions-14 P1 live_t1 T1 19/22 now quoted (claims.md:17,67; REPORT.md:158), but live_t1 was the brain-5 tuning set and isn't labeled dev
2. decisions-25 P1 builder_data_decisions.md spends up to $70 on a code-gold gap 184c80f already closed (2,224 states / ~9.7k decisions)
3. decisions-17 P1 noul 37.6% true; score levels 4-5 = 1.9% of score gold
4. decisions-13 P1 route_acc still r2 .864 'top-1', not it2 with tau stated — pitch/claims.md:13
5. decisions-4 P1 noul option order flips with criteria presence — ml/src/brain/generic_decide.py
6. decisions-3 / decisions-5 P1 route regression runner and backend parity — cloud/builder_decisions.md

## Highest-leverage next moves
- Label live_t1 a dev suite in claims/REPORT, or freeze a held-out live set before quoting 19/22 (decisions-14).
- Re-scope the data-decisions brief from full_gen.md@184c80f before it spends (decisions-25).
- Rebalance noul/score labels in split or loss weights before the decisions Tinker run (decisions-17).
- Fix REPORT.md:71,170 '301' and caveat .658 (decisions-23/-11); claims.md:13 to it2 with gating (decisions-13).
