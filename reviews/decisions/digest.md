# decisions — digest (pass 15)

Heads: main d7c192f (default router it2, tau .65), data-pipeline 0ce9ea6 (it2 untied export, evalcheck v2 incl. evals/external), cloud/decisions 6d395df unchanged, wip/local 367d450 (no lane diff).
Resolved: decisions-20 (default it2 has 0 live_t1 overlaps; route_v1 via clean_both).

## Open P0/P1
1. decisions-21 P0 Routers trained on near-duplicates of DeskMind and HobbyLM sealed requests — pitch/claims.md:25-28
2. decisions-13 P1 route_acc stale (r2 .864 vs default it2) and gating unstated — pitch/claims.md:13
3. decisions-14 P1 live_t1 fixes fitted on live_t1 failures; live_t1_pass not held out — pitch/claims.md:17
4. decisions-17 P1 Per-family noul/score gold priors still skewed — training/decisions/families/*
5. decisions-12 P1 cloud/decisions not rebased — ml/src/brain/decision.py
6. decisions-4 P1 noul option order flips with criteria presence — ml/src/brain/generic_decide.py
7. decisions-3 P1 Route regression renderer/n=140 — cloud/builder_decisions.md
8. decisions-5 P1 Before/after must use one backend/precision — cloud/builder_decisions.md

## Highest-leverage next moves
- Default to it2b (0 external overlaps) or clean-subset scoring before HobbyLM/DeskMind live runs (decisions-21).
- Update claims.md route row to the shipped router, with gating stated (decisions-13).
- Label-first sampling per family before the full decisions run (decisions-17); rebase cloud/decisions (decisions-12).
- Rerun DeskMind brain-4b typed-decisions with normalization before quoting .658 (decisions-11).
