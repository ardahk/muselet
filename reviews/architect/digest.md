# architect digest - pass 51 (2026-10-24T23:22Z)
Reviewed: main 46b97f5 (harness proxy close bound), wip/local 719907a, safety-architect27 4edcba5, safety-brain12/18/38, safety-planner28, brain-9 e9e9b42, live-cases fa9c374. New: architect-34 and architect-35 (both P2, on the architect-27 fix branch). The Premiere beat is now out of the 3:00 demo cut, so architect-26 and architect-27 are lower demo risk.

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
5. Re-run the decisions calibrated JevBench + TD eval (~$0.3, within the $148 stop).
