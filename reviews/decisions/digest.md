# decisions — digest (pass 3)

Heads: main 2920225, cloud/decisions 3a865a0 (new: Tinker System One backend), cloud/data-pipeline 5371185.
All open findings re-verified (pass-3 lines in findings.jsonl): none fixed. Branch-only (still live): decisions-1, -9, -10 (cloud/data-pipeline).
Verified OK: tinker_backend.py scores row choice_pos-1 like vendor tinker_decisions.py:36-49 and imports GenericRenderer.

## Open P0/P1
1. decisions-1 P1 Decontam index lacks JevBench/typed-decisions; no 13-gram or option-set test — training/src/muselet_train/decontam.py (data-pipeline)
2. decisions-12 P1 cloud/decisions forked pre-f584cb2; merge drops scorer, venv and split_model fixes — ml/src/brain/decision.py
3. decisions-9 P1 it2 terse-ASK top-up targets route_v1 ASK items; decontam misses swaps — training/src/muselet_train/gen.py (data-pipeline)
4. decisions-3 P1 Route regression would be measured with the wrong renderer and n=140 — cloud/builder_decisions.md
5. decisions-5 P1 Before/after numbers would mix MLX-4bit and Tinker-bf16 — cloud/builder_decisions.md
6. decisions-10 P1 it2 retrain plan has no token/$ estimate — training/reports/phase1_it2_plan.md (data-pipeline)
7. decisions-4 P1 noul option order flips with criteria presence — ml/src/brain/generic_decide.py
8. decisions-2 P1 Identical-option-set rule undefined/degenerate — cloud/builder_decisions.md

## Highest-leverage next moves
- Rebase cloud/decisions on main before anything is merged (decisions-12).
- Land a decisions decontam (JevBench@609a664 + td@80cb93a, 13-gram + defined option-set rule) before generation.
- Baseline = TinkerDecider base_model on the same backend; route regression via eval_route/router_check, paired on val.
- Strip route_v1 wording from IT2_ASK_STYLE; post it2 est_usd and get the >$25 OK.
