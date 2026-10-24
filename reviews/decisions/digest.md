# decisions — digest (pass 21)

Heads: cloud/decisions e125c13 (full generation done, $52.89/$57, 6,754 decisions uploaded to jonsnov/muselet-decisions-v1), main c949565 (briefs only), wip/local 4ec066f (no lane diff).

## Open P0/P1
1. decisions-22 P1 Pilot-as-reference decontam deletes 87% of code-gold data — training/decisions/full_run.py:287
2. decisions-17 P1 Label priors skewed: noul 34% true, score level 5 only 3/1608 — training/decisions/families/*
3. decisions-13 P1 route_acc quotes r2 .864 'top-1', not the serving it2, gating unstated — pitch/claims.md:13
4. decisions-14 P1 live_t1 fixes fitted on live_t1 failures; live_t1_pass not held out — pitch/claims.md:17
5. decisions-12 P1 cloud/decisions not rebased — ml/src/brain/decision.py
6. decisions-4 P1 noul option order flips with criteria presence — ml/src/brain/generic_decide.py
7. decisions-3 P1 Route regression renderer/n=140 — cloud/builder_decisions.md
8. decisions-5 P1 Before/after must use one backend/precision — cloud/builder_decisions.md

## Highest-leverage next moves
- Before any Tinker run: drop include_pilot and re-run decontam/split/datums from records_labeled.jsonl ($0) (decisions-22).
- Rebalance noul per family (reweight or subsample to ~50%) in the split stage (decisions-17).
- Write the decisions Tinker hypothesis + estimate (report projects ~$12 per 20k datums; ~$4 for 6.8k) with 30% route replay.
- claims.md:13 to it2 with gating stated (decisions-13); label live_t1 as dev or freeze a holdout (decisions-14).
