# decisions — digest (pass 16)

Heads: main fbd5aa0 (AGENTS.md competitor-bench router policy), data-pipeline 735686f (it2 external overlaps per id), pitch-4 6393857 (claims §1b disclosures, unmerged), cloud/decisions 6d395df unchanged, wip/local 2f26223 (no lane diff).
decisions-21 fix is on cloud/pitch-4 (verified DeskMind hits are CJK normalizer artifacts); resolves on merge.

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
- Merge pitch-4; run HobbyLM r4 / DeskMind diag with it2 only (decisions-21).
- claims.md:13 still quotes r2 .864 'top-1': switch to it2 and state ungated vs tau .65 (decisions-13).
- Label-first sampling per family before the full decisions run (decisions-17); rebase cloud/decisions (decisions-12).
- Rerun DeskMind brain-4b typed-decisions with normalization before quoting .658 (decisions-11).
