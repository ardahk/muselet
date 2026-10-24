# architect digest - pass 53 (2026-10-24T23:50Z)
Reviewed: main 18c139f (merged planner-lora #48, planner-think #56 default off, live-cases #57, brain-12/18/27/38, bench-28) and planner-lora 79f0a97 (MLX export: untied lm_head written, Mac smoke skipped). The default serving config is unchanged (base planner, few-shot, k=1, THINK=0). The LoRA was trained without few-shot or retrieval, so its Mac matrix must pass `--planner-fewshot none` via serve_brain's extra args (planner_offline already uses few_shot=None). No new findings.

## Open P1 (ranked)
1. architect-29 - No competitor benchmark number exists - pitch/claims.md
2. architect-32 - HobbyLM replay drops skips from denominator vs /125 claim - bench/hobbylm/replay.py
3. architect-33 - Done verifier default on with unfitted 0.5 threshold - ml/src/brain/orchestrator.py (cloud/planner-verify)
4. architect-24 - No goal-level done check on main (fix on planner-verify) - ml/src/brain/orchestrator.py
5. architect-28 - Retrieval bank / demo gate pass paraphrases of holdout goals - ml/src/brain/plan_bank.py
6. architect-27 - premiere_command doesn't verify; partial fix on safety-architect27 (Premiere out of demo) - app/Sources/HandsKit/Skills.swift
7. architect-26 - Planner prompt teaches cmd+t as Premiere transition - prompts/planner_system.md
8. architect-13 - System One tinker backend reports as 'muselet' - bench/systemone/cli.py
9. architect-8 - No Mac parity result for it2 - evals/router_check.py
(P2: 35, 34, 31, 30, 20, 15, 16)

## Highest-leverage next moves
1. HobbyLM r4 (it2) on the Mac, no --exclude-kind, quote passes/125 with skips as fails. ~1.5 h. This is the only competitor claim within reach.
2. planner-verify: fit VERIFY_P on labelled final states or merge with VERIFY_DONE=off. ~30 min.
3. Before merging safety-architect27: probe Premiere's real Window menu titles, and confirm only export. ~15 min on the Mac.
4. Run the planner-lora / think Mac matrix on paraphrase-deduped holdouts. ~1 h.
5. Mac MLX 4-bit decisions run (jonsnov/muselet-decisions-4b-mlx4 @ 8a8807d, T=1) on JevBench + TD through the same shim as the DeskMind ref. Quote it only as a tie or win against the SE. ~30 min.
