# planner lane — pass 14 (main bb494af = brain-3 + finance-3 + advisor-3 merged; wip c85a000)

Resolved: planner-21. web_ax_pending handling is on main via brain-3. 227 non-MLX tests pass on main.
New: evals/planner_offline.py (28 scenarios, bb5a80b) reviewed. The few-shot examples don't overlap any scenario goal, so there is no leakage. The grader doesn't match the runtime (planner-22).

## Open P1 (ranked)
1. planner-20 P1 — The harness's own `done` rejection counts toward the 3-failed-turns guard, so a recovered task can end in "I'm stuck" — now on main, ml/src/brain/orchestrator.py L1087-1096
2. planner-22 P1 — The offline planner benchmark scores lines the runtime would accept (prose, missing `skill` prefix) as invalid, which skews the knob comparisons — evals/planner_offline.py
3. planner-6 P1 — Premiere runs via keyboard shortcuts only; the 8766 UXP bridge isn't connected, so results can't be verified — app/Sources/HandsKit/Skills.swift

## Highest-leverage next moves
- orchestrator.py: skip fail_streak += 1 on the done-rejection turn (one flag).
- planner_offline.py: apply dsl.action_line before BatchCutter and grade, so the benchmark mirrors the runtime before any knob or model is picked.
- Premiere: add an expect to each premiere_command, or connect the bridge for add_marker and export_sequence.
