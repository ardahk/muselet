# planner lane — pass 25 (main 7147694, wip 5764a0d = main in this lane, new cloud/grounder-wire afb12a6)

Pass 25: 1 new P2 (planner-26). main: holdout-2 (12 scenarios) was correctly written after holdout-1 was used to derive rules 16-18, so treat holdout-1 as tuning data from now on, and the bench now passes few_shot=None. grounder-wire: the `click "<target>"` DSL goes through a fresh screenshot and the grounder, with a confirm for dangerous labels and screenshots deleted afterwards; the DSL parse and serialize round-trip is consistent.

## Pass 24 notes

Pass 24: no new findings, and the open findings are unchanged.

Resolved: planner-23 on main (the volume fast path was dropped in the merge). 89 tests pass on main, including the planner-20 repro.

## Open P1 (ranked)
1. planner-24 P1 (main, new via PR #16) — calculator digits are sent as raw global `keys` after an unverified `open Calculator`, so they can land in the user's frontmost document — ml/src/brain/orchestrator.py L954-957
2. planner-6 P1 (main) — Premiere is still keyboard shortcuts only, with the 8766 bridge not connected — app/Sources/HandsKit/Skills.swift

## Highest-leverage next moves
- orchestrator._deliver_calc: replace the raw `keys` acts with `skill type_text text="<expr>="` (Calculator is a keystroke_app on main, so the target is checked and not_frontmost returned).
- planner.py: build OpConstraint at warmup (planner-25, P2).
- Copy reviews/planner/tests/test_planner20_done_reject_streak.py into ml/tests as a regression test.
- Premiere: add an expect to each premiere_command, or connect the bridge.
