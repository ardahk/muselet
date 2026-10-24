# planner lane — pass 33 (main c949565, wip 4ec066f = main in this lane, decisions e125c13)

Pass 33: no lane changes; main only added briefs, and decisions e125c13 doesn't touch this lane. I re-checked the open findings on main and none has changed: planner-24 L984, planner-26 L289, planner-27 L1516, planner-25 planner.py L334, planner-6. Note for the comms-builder brief: send confirmations for contacts-first messaging and email drafting already go through sendgate.py (planner-lane safety). Keep any new messaging skills behind that gate.

## Pass 32 notes

Pass 32: no lane changes; main only touched AGENTS.md. I re-checked the open findings on main and none has changed: planner-24 L984, planner-26 L289, planner-27 L1516, planner-25 planner.py L334, planner-6.

## Pass 31 notes

Pass 31: no new findings. brain-6 (#21) is merged, so planner-27 is now on main (L1516). 82d94d9 adds Zen, Vivaldi, Opera and Orion to the browsers whose chat and mail tabs get send confirmations, with tests; no issues. Open findings on main are otherwise unchanged (planner-24 L984, planner-26 L289, planner-25 planner.py L334, planner-6).

## Pass 30 notes

Pass 30: 1 new P2 (planner-27). brain-6 adds sendgate.py: Enter and send confirms now cover chat and mail apps and browser tabs for them, not just Mail, Messages and Slack. It also adds a safety gate on grounded clicks (target label, composer or payment context, the AX label under the point, otherwise OCR, failing closed). It looks correct; 126 focused tests pass. Open findings on main are unchanged (planner-24 L977, planner-26 L289, planner-25 planner.py L334, planner-6).

## Pass 29 notes

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
