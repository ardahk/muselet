# planner lane — pass 29 (main b625ceb, wip 49f808f = main in this lane, data-pipeline 512cce0)

Pass 29: no lane changes; main only merged pitch-4 (docs) and the spend-guard fix. I re-checked the open findings on main: planner-24 (orchestrator.py L977), planner-26 (L289) and planner-25 (planner.py L334) are unchanged, and planner-6 is unchanged.

## Pass 28 notes

Pass 28: no lane changes; main only touched AGENTS.md (competitor benchmark overlap rule), and pitch-4 and data-pipeline don't touch this lane. I re-checked the open findings on main: planner-24 (orchestrator.py L977), planner-26 (L289) and planner-25 (planner.py L334) are unchanged, and planner-6 is unchanged.

## Pass 27 notes

Pass 27: no lane changes; main only touched AGENTS.md and the serve_brain router default. I re-checked all open findings on main: planner-24 (orchestrator.py L977), planner-26 (L289) and planner-25 (planner.py L334) are unchanged, and planner-6 is unchanged.

## Pass 26 notes

Pass 26: no new findings. grounder-wire (#19) and pitch-3 (#18) are merged. The prompt now lists click "<description>" below skills, keyboard shortcuts and pressing elements, and rules 16-18 are in planner_fewshot.md. planner-26 is now on main. Calculator is at L977.

## Pass 25 notes

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
