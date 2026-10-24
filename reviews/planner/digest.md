# planner lane — pass 18 (main 758a017, wip a3f82f1 = main in this lane, brain-4 dfb66a3, hobby-gaps 929b931)

Resolved: planner-23 on hobby-gaps (the volume fast path now requires volume context; repro re-run).
Reviewed: brain-4 dfb66a3 (history default changed to dsl; the opt-in escalation planner takes over at fail_streak 2 and stops after it fails twice). It looks correct, and 78 tests pass with the mlx stub. main c39df67 widens a holdout accept pattern to `type #2 "github.com" enter`. That answer is legitimately valid, but grader edits made after holdout results are seen should be logged, to keep the holdout honest.

## Open P1 (ranked)
1. planner-24 P1 (hobby-gaps) — calculator keys are sent as global keys before Calculator is confirmed frontmost, so they can land in the user's document — ml/src/brain/orchestrator.py L719-724
2. planner-20 P1 (main) — the harness's own `done` rejection counts toward the "I'm stuck" guard. Fixed on cloud/brain-4, not yet on main — ml/src/brain/orchestrator.py
3. planner-6 P1 (main) — Premiere is still keyboard shortcuts only, with the 8766 bridge not connected — app/Sources/HandsKit/Skills.swift L256-261, 756

## Highest-leverage next moves
- Merge cloud/brain-4 (closes planner-20), and copy reviews/planner/tests/test_planner20_done_reject_streak.py into ml/tests.
- hobby-gaps: put `expect app "Calculator"` on the open action and abort before any keys if it fails.
- brain-4: build OpConstraint at warmup, for both the main and the escalation planner (planner-25).
- Premiere: add an expect to each premiere_command, or connect the bridge.
