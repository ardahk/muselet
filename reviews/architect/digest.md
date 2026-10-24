# architect digest - pass 50 (2026-10-24T23:08Z)
Reviewed: main a97fcba (merged it3 opt-in #52, W9 safety #46, docs-demo-2 #53), wip/local, brain-9 3f9718b (hidden 'browser' arg skipped by arg_signature, so router/ARGS/planner render parity holds; planner warm task), safety-bench28 a0c456e (3 unsafe retrieval demos excluded), safety-brain27 ac43219 (composer-click confirm), planner-verify d22b9a9 (architect-33 unchanged), planner-think 3677348 (merge only), memory/memory-lt. No new findings. architect-23 resolved.

## Open P1 (ranked)
1. architect-29 - No competitor benchmark number exists - pitch/claims.md
2. architect-32 - HobbyLM replay drops skips from denominator vs /125 claim - bench/hobbylm/replay.py
3. architect-27 - premiere_command no Timeline focus, always reports success - app/Sources/HandsKit/Skills.swift
4. architect-33 - Done verifier default on with unfitted 0.5 threshold - ml/src/brain/orchestrator.py (cloud/planner-verify)
5. architect-24 - No goal-level done check on main (fix on planner-verify) - ml/src/brain/orchestrator.py
6. architect-28 - Retrieval bank / demo gate pass paraphrases of holdout goals - ml/src/brain/plan_bank.py
7. architect-26 - Planner prompt teaches cmd+t as Premiere transition - prompts/planner_system.md
8. architect-13 - System One tinker backend reports as 'muselet' - bench/systemone/cli.py
9. architect-8 - No Mac parity result for it2 - evals/router_check.py
(P2: 31 still on main after W9 merge, 30, 20, 15, 16)

## Highest-leverage next moves
1. Run HobbyLM r4 (it2) on the Mac without --exclude-kind and quote passes/125 with skips counted as fails (architect-32). ~1.5 h. This is the only competitor claim within reach.
2. Before merging planner-verify: fit VERIFY_P on labelled final states (v2-tune + live_t1), target false reject <= 5%; otherwise merge with VERIFY_DONE=off. ~30 min.
3. Run the planner-lora / think Mac matrix on paraphrase-deduped holdouts (architect-28), one model process at a time. ~1 h.
4. Premiere hardening: Timeline focus (shift+3) plus a cmd+d prompt fix, then rehearse. ~20 min.
5. Re-run the decisions calibrated JevBench + TD eval (~$0.3, within the $148 stop).
