# decisions — digest (pass 10)

Heads: main 26ff05b (brain-5 merged, route parity reference v2), cloud/decisions 91a62c2 (amendment-2 generators, reasoning-teacher gate: gpt-5.4-nano 98.7%), data-pipeline eae3b7e (it2 H9), hobby-gaps 861b991, wip/local 2c79363 (no lane diff vs main).
Resolved this pass: decisions-15 (render via server_questions), -16 (answer-leaking options).

## Open P0/P1
1. decisions-19 P1 Teacher-gold authoring cost projects ~$900 for 20k; report omits it — training/decisions/build.py
2. decisions-18 P1 Recommended router config measured on the folded export f39efe4 fixes — tools/serve_brain.sh
3. decisions-17 P1 Per-family noul/score gold priors still skewed; score never 5-6 levels — training/decisions/families/*
4. decisions-12 P1 cloud/decisions not rebased; merge drops scorer, venv and split_model fixes — ml/src/brain/decision.py
5. decisions-14 P1 live_t1 fixes fitted on live_t1 failures; live_t1_pass not held out — pitch/claims.md:17
6. decisions-13 P1 route_acc claimed as top-1 but eval-route accuracy is tau-gated — pitch/claims.md:13
7. decisions-10 P1 it2 retrain plan has no token/$ estimate — training/reports/phase1_it2_plan.md
8. decisions-4 P1 noul option order flips with criteria presence — ml/src/brain/generic_decide.py
9. decisions-3 P1 Route regression renderer/n=140 — cloud/builder_decisions.md
10. decisions-5 P1 Before/after must use one backend/precision — cloud/builder_decisions.md

## Highest-leverage next moves
- Price authored decisions before the full run; cumulative ledger; lead picks author model / teacher-gold share (decisions-19).
- Re-export main-final with untie and re-run router_check before serve_brain.sh numbers are quoted (decisions-18).
- Label-first sampling per family (noul 50/50, score 3..6 levels) and per-family histograms in the report (decisions-17).
- Rebase cloud/decisions on main (decisions-12); Tinker estimate incl. route replay + epochs (decisions-7).
- Pitch: ungated top-1 or dev-fitted-tau accuracy for route_acc; label live_t1 as dev or freeze a holdout (decisions-13/14).
