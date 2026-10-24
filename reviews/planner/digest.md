# planner lane — pass 16 (main 2920225 = wip 3e03686; cloud/decisions, pitch-2, data-pipeline: nothing changed in this lane)

Pass 16: no new findings. wip/local's tree matches main. cloud/decisions only touches router/decision code and bench, cloud/pitch-2 only docs, and cloud/data-pipeline only data. planner-20 (the repro still fails) and planner-6 are still open.

## Pass 15 notes

I re-checked every finding against main. Planner-2, -3, -4, -5, -7, -8, -9, -10, -11, -12, -13, -14, -15, -16, -17, -18 and -21 are fixed on main and confirmed by code or a passing test. planner-22 was fixed in 2920225. planner-1 and -19 were superseded. No finding is resolved only on a branch.
Tests: test_planner_loop now runs on Linux with an import stub (see tests/test_planner20_done_reject_streak.py). Results: 77 passed and the 1 planner-20 repro failed.
New merges reviewed: the planner bench grading now matches runtime (good); planner_fewshot.md moved to prompts/ and is only used via --system-extra; decision_chunking/generic_decide belong to the router lane.

## Open P1 (ranked)
1. planner-20 P1 — The harness's own `done` rejection counts toward the 3-failed-turns guard ("I'm stuck") — ml/src/brain/orchestrator.py L1087-1096 (repro: tests/test_planner20_done_reject_streak.py)
2. planner-6 P1 — Premiere runs via keyboard shortcuts only; the 8766 UXP bridge isn't connected, so results can't be verified — app/Sources/HandsKit/Skills.swift L256-261, 756

## Highest-leverage next moves
- orchestrator.py: skip fail_streak += 1 on the done-rejection turn. Copy the repro test into ml/tests as a regression test.
- Premiere: add an expect to each premiere_command (`appears "Export"`, marker count), or connect the bridge for add_marker and export_sequence.
