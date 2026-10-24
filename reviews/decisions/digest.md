# decisions — digest (pass 19)

Heads: main 82d94d9 (brain-6 + sendgate merged; no lane diff), data-pipeline 512cce0 (CJK-aware evalcheck, it2 v3 report), cloud/decisions 6d395df unchanged, wip/local 49f808f (no lane diff); brain-6 780f49d = send/click safety gates, no router/decision changes.
Resolved this pass: decisions-21 (competitor-bench contamination disclosed and policed; it2 0 on HobbyLM r4 and DeskMind).

## Open P0/P1
1. decisions-13 P1 route_acc quotes r2 .864 'top-1', not the serving it2, gating unstated — pitch/claims.md:13
2. decisions-14 P1 live_t1 fixes fitted on live_t1 failures; live_t1_pass not held out — pitch/claims.md:17
3. decisions-17 P1 Per-family noul/score gold priors still skewed — training/decisions/families/*
4. decisions-12 P1 cloud/decisions not rebased — ml/src/brain/decision.py
5. decisions-4 P1 noul option order flips with criteria presence — ml/src/brain/generic_decide.py
6. decisions-3 P1 Route regression renderer/n=140 — cloud/builder_decisions.md
7. decisions-5 P1 Before/after must use one backend/precision — cloud/builder_decisions.md

## Highest-leverage next moves
- claims.md:13: quote it2 on route_v1_clean, saying ungated (.961 Tinker argmax) or tau .65 (.913) (decisions-13).
- Label live_t1 as a dev suite or freeze a held-out live set before the morning run (decisions-14).
- Label-first sampling per family and 3-6 score levels before the full decisions run (decisions-17); rebase cloud/decisions (decisions-12).
- Rerun DeskMind brain-4b typed-decisions with normalization before quoting .658 (decisions-11).
