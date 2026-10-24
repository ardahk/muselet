# decisions — digest (pass 2)

`cloud/decisions` still absent. New since pass 1: main bb494af (evals/router_check.py: route render+logit parity,
dev-fitted tau, route_v1 at own tau — fine for route parity/calibration), cloud/data-pipeline 70b7d1b (it2), cloud/bench f584cb2.
Pass-1 findings re-checked: all still open (decontam.py, generic_decide.py, brief unchanged).

## Open P0/P1
1. decisions-1 P1 Decontam index lacks JevBench/typed-decisions; no 13-gram or option-set test — training/src/muselet_train/decontam.py
2. decisions-9 P1 it2 terse-ASK top-up targets route_v1 ASK items; decontam misses swaps — training/src/muselet_train/gen.py
3. decisions-3 P1 Route regression would be measured with the wrong renderer and n=140 — cloud/builder_decisions.md
4. decisions-5 P1 Before/after benchmark numbers would mix MLX-4bit and Tinker-bf16 — cloud/builder_decisions.md
5. decisions-10 P1 it2 retrain plan has hypotheses but no token/$ estimate — training/reports/phase1_it2_plan.md
6. decisions-4 P1 noul option order flips with criteria presence — ml/src/brain/generic_decide.py
7. decisions-2 P1 Identical-option-set rule is degenerate on benchmark option sets — cloud/builder_decisions.md

## Highest-leverage next moves
- Strip route_v1 wording from IT2_ASK_STYLE and judge H2 on val before generating it2 data.
- Post it2 est_usd and get the >$25 OK; reserve the decisions-run budget (~$15/epoch) explicitly.
- Write the decisions decontam (JevBench + td, 13-gram + defined option-set rule) before any generation.
- Route regression via eval_route.py / router_check.py (route renderer), paired on val.
- Rerun DeskMind rows with f584cb2 scorer before any comparison claim.
