# planner lane — pass 22 (main 26ff05b = brain-5 merged + argfix off-words + route parity; wip 2c79363 = main in this lane; hobby-gaps 861b991 = main merge)

Pass 22: no new findings. With brain-5 merged, the 78 tests (including the planner-20 repro) pass on main.

Resolved: planner-20 on main (the repro passes, 78 tests pass). brain-5 5cef455 treats `not_frontmost` from launch skills as a terminal failure with a clear bubble, and it looks correct (78 tests pass after the main merge).

## Open P1 (ranked)
1. planner-24 P1 (hobby-gaps 861b991) — _deliver_calc sends raw global `keys` after an unverified `open Calculator` — ml/src/brain/orchestrator.py L820-823
2. planner-6 P1 (main) — Premiere is still keyboard shortcuts only, with the 8766 bridge not connected — app/Sources/HandsKit/Skills.swift

## Highest-leverage next moves
- hobby-gaps: switch _deliver_calc to `skill type_text` (Calculator is a keystroke_app on main), which checks the target and returns not_frontmost.
- planner.py: build OpConstraint in Planner.__init__ or at warmup (planner-25, P2; now on main).
- Copy reviews/planner/tests/test_planner20_done_reject_streak.py into ml/tests as a regression test.
- Premiere: add an expect to each premiere_command, or connect the bridge.
