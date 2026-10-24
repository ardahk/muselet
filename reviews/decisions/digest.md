# decisions — digest (pass 12)

Pass 12: data-pipeline 0c1ca3d extends the evalcheck gate to evals/external (OK); wip/local 0db1681 moves GenericMLXDecider MLX work onto one worker thread (render path unchanged, decide() routes via decide_many; OK). No new findings.

Heads: main d502b78 (hobby-gaps merged, route_v1_clean, serve_brain r2), cloud/decisions 6d395df (amendment 3, mini-check), data-pipeline 19737e1 (evalcheck hard gate, pre-flight $ abort), wip/local c7c04ce (no lane diff vs main).
Resolved this pass: decisions-18 (r2 re-export + tau .45), -19 (budget $57 with authored costs), -10 (pre-flight estimate + abort).

## Open P0/P1
1. decisions-20 P0 Shipped router trained on near-duplicates of 37 route_v1, 10 live_t1 cases — pitch/claims.md:13,17
2. decisions-17 P1 Per-family noul/score gold priors still skewed; score never 5-6 levels — training/decisions/families/*
3. decisions-12 P1 cloud/decisions not rebased; merge drops scorer, venv and split_model fixes — ml/src/brain/decision.py
4. decisions-14 P1 live_t1 fixes fitted on live_t1 failures; live_t1_pass not held out — pitch/claims.md:17
5. decisions-13 P1 route_acc claimed as top-1 but eval-route accuracy is tau-gated — pitch/claims.md:13
6. decisions-4 P1 noul option order flips with criteria presence — ml/src/brain/generic_decide.py
7. decisions-3 P1 Route regression renderer/n=140 — cloud/builder_decisions.md
8. decisions-5 P1 Before/after must use one backend/precision — cloud/builder_decisions.md

## Highest-leverage next moves
- claims.md: route_acc on route_v1_clean (103), live pass on a 33-case clean live_t1 or frozen holdout for trained-router configs (decisions-20/13/14).
- Label-first sampling per family (noul 50/50, score 3..6 levels) before the full run (decisions-17).
- Rebase cloud/decisions on main before merge (decisions-12).
- Train some noul without criteria or normalise runtime order (decisions-4).
