# decisions — digest (pass 22)

Heads: cloud/decisions 184c80f (merged main; decontam re-run, multi-task trainer + dev-only calibration), data-pipeline 6c1e565 (route_v2 frozen, it3 prep), report dffa733, brain-7 13432fe (compose_text router:false, catalog parity kept), main c949565.
Resolved this pass: decisions-22 (code-gold restored: 2,224 states, all families), decisions-12 (main merged into cloud/decisions).

## Open P0/P1
1. decisions-17 P1 Label priors skewed: noul 37.6% true, score levels 4-5 = 1.9% — training/decisions/families/*
2. decisions-13 P1 route_acc quotes r2 .864 'top-1', not serving it2; gating unstated — pitch/claims.md:13
3. decisions-14 P1 live_t1 fixes fitted on live_t1 failures; live_t1_pass not held out — pitch/claims.md:17
4. decisions-4 P1 noul option order flips with criteria presence — ml/src/brain/generic_decide.py
5. decisions-3 P1 Route regression renderer/n=140 — cloud/builder_decisions.md
6. decisions-5 P1 Before/after must use one backend/precision — cloud/builder_decisions.md

## Highest-leverage next moves
- Reweight noul to ~50% per family and upsample score levels 4-5 in the split/trainer before the Tinker run (decisions-17).
- Report route regression on route_v1_clean + route_v2 for base, it2 and the multi-task model with one runner (decisions-3/-5).
- Add route_v2 to decisions decontam (decisions-24); fix REPORT.md:166 and the .658 caveat (decisions-23/-11).
- claims.md:13 to it2 with gating stated (decisions-13); label live_t1 as dev or freeze a holdout (decisions-14).
