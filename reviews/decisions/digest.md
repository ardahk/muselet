# decisions — digest (pass 6)

Pass 6: main 758a017 (pitch-2 merged, brain-5 brief), brain-4 dfb66a3 (planner escalate; no route/ARGS change), wip/local + hobby-gaps no lane diff.
Heads (pass 5): main 28dc259, cloud/data-pipeline 80cb13f, cloud/decisions 3a865a0, cloud/brain-4 3aca368, wip/local e1701a3 (no lane diff vs main).
Resolved this pass: decisions-9 (abstract it2 prompts + short_edit1 decontam + val-only selection; re-ran the matcher).
Checked OK: data-pipeline 80cb13f ARGS datums weight only answer+<|im_end|>, matching DecisionEngine.args prefilled think block (test_route_render.py); brain-4 split ARGS model uses its own tokenizer/body/lm_head end to end; router_check ARGS e2e matches cli.eval_route rules.

## Open P0/P1
0. decisions-14 P1 brain-5 fixes fitted on live_t1 failures; live_t1_pass then not held out — cloud/builder_brain5.md / pitch/claims.md:17
1. decisions-1 P1 Decontam index lacks JevBench/typed-decisions; no 13-gram or option-set test — training/src/muselet_train/decontam.py (data-pipeline)
2. decisions-12 P1 cloud/decisions forked pre-f584cb2; merge drops scorer, venv and split_model fixes — ml/src/brain/decision.py
3. decisions-13 P1 route_acc claimed as top-1 but eval-route accuracy is tau-gated — ml/src/brain/cli.py / pitch/claims.md:13
4. decisions-10 P1 it2 retrain plan has no token/$ estimate — training/reports/phase1_it2_plan.md (data-pipeline)
5. decisions-3 P1 Route regression would be measured with the wrong renderer and n=140 — cloud/builder_decisions.md
6. decisions-5 P1 Before/after numbers would mix MLX-4bit and Tinker-bf16 — cloud/builder_decisions.md
7. decisions-4 P1 noul option order flips with criteria presence — ml/src/brain/generic_decide.py
8. decisions-2 P1 Identical-option-set rule undefined/degenerate — cloud/builder_decisions.md

## Highest-leverage next moves
- Freeze a held-out live set before brain-5 lands; quote that, not live_t1 (decisions-14).
- Rebase cloud/decisions on main before merging (decisions-12).
- Add JevBench@609a664 + typed-decisions@80cb93a text, 13-gram and a defined option-set rule to decontam before decisions data is generated.
- Quote accuracy_top1_ungated as router top-1 in the pitch (decisions-13).
- Put est_usd/tokens + lead OK in phase1_it2_plan.md before launching it2 (decisions-10).
