# planner lane — pass 17 (main 28dc259, wip e1701a3, new cloud/brain-4 3aca368, cloud/hobby-gaps 14ff59b)

main 28dc259 adds 14 holdout scenarios to the planner bench (--set holdout). They don't overlap the tuning set and the few-shot examples aren't scenarios, so there's no leakage. cloud/brain-4 fixes planner-20: my repro passes there.

## Open P1 (ranked)
1. planner-23 P1 (hobby-gaps) — route() maps any "up"/"down" utterance ("scroll down", "look up flights") to change_volume — ml/src/brain/orchestrator.py L207-225
2. planner-24 P1 (hobby-gaps) — calculator digits are sent as global keys before Calculator is confirmed frontmost, so they can land in the user's document — ml/src/brain/orchestrator.py L692-745
3. planner-20 P1 (main) — the harness's own `done` rejection counts toward the "I'm stuck" guard. Fixed on cloud/brain-4 dbc699d, not yet on main
4. planner-6 P1 (main) — Premiere is still keyboard shortcuts only, with the 8766 bridge not connected — app/Sources/HandsKit/Skills.swift L256-261, 756

## Highest-leverage next moves
- Merge cloud/brain-4 (closes planner-20), and copy reviews/planner/tests/test_planner20_done_reject_streak.py into ml/tests.
- hobby-gaps, before merge: add a volume-context check to the route() fast path, and add `expect app "Calculator"` before sending calculator keys.
- brain-4: build OpConstraint at warmup, not inside the first plan() (planner-25, P2).
- Premiere: add an expect to each premiere_command, or connect the bridge.
