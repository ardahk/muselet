# decisions — digest (pass 9)

Heads: main d514300 (brain-4 merged, serve_brain.sh), data-pipeline f13aa6d (lm_head untie on export), brain-5 b752261 (main merged), wip/local b63699f (same lane diff as main), cloud/decisions c08a96d unchanged.

## Open P0/P1
1. decisions-18 P1 Recommended router config measured on the folded export that f39efe4 fixes — tools/serve_brain.sh
2. decisions-15 P1 render_records feeds raw wire questions; every choice/score datum KeyErrors — training/decisions/render.py
2. decisions-16 P1 Code-gold options leak the answer via descriptions, padding and verbatim values — training/decisions/families/numeric.py, core.py
3. decisions-17 P1 Per-family noul/score gold priors violate SPEC balance — training/decisions/families/*
4. decisions-12 P1 cloud/decisions not rebased; merge drops scorer, venv and split_model fixes — ml/src/brain/decision.py
5. decisions-14 P1 brain-5 fixes fitted on live_t1 failures; live_t1_pass not held out — pitch/claims.md:17
6. decisions-13 P1 route_acc claimed as top-1 but eval-route accuracy is tau-gated — ml/src/brain/cli.py
7. decisions-10 P1 it2 retrain plan has no token/$ estimate — training/reports/phase1_it2_plan.md
8. decisions-4 P1 noul option order flips with criteria presence (TD: 200 noul without criteria) — ml/src/brain/generic_decide.py
9. decisions-3 P1 Route regression renderer/n=140 — cloud/builder_decisions.md
10. decisions-5 P1 Before/after must use one backend/precision — cloud/builder_decisions.md

## Highest-leverage next moves
- Re-export main-final with untie, re-run router_check (parity, tau, route_v1, trained-vs-base ARGS) before serve_brain.sh numbers are quoted (decisions-18).
- Fix render_records (server_questions) before any datums/upload (decisions-15).
- Rewrite generators: neutral option text, computed distractors, label-first sampling; add description-only/verbatim/prior baselines to the report (decisions-16/17).
- Train some noul without criteria (true-first Yes/No) or normalise runtime order (decisions-4).
- Rebase cloud/decisions on main (decisions-12); write the Tinker $ estimate incl. route replay before training (decisions-7).
