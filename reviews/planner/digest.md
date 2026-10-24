# planner lane — pass 9 (main 76a03c1, wip 34ddf5f, cloud/brain-3 14a3f52, finance-3 31be399, advisor-3 ca93147)

Reviewed with no issues: main's prompt rules 14-15 (cmd+n for a new document; never repeat a failed action a third time), brain-3's action_line filter and skill auto-prefix (prose/tags are no longer counted toward the 5-action cap), the script failure copy, absolute volume, compound fast path, and finance-3's poll for the opened table.

## Open P1 (ranked)
1. planner-20 P1 — Harness's own done-rejection counts toward the 3-failed-turns loop guard, so a recovered task can end in "I'm stuck" — ml/src/brain/orchestrator.py@brain-3 L1080-1105
2. planner-6 P1 — Premiere runs via keyboard shortcuts only; the 8766 UXP bridge isn't connected, so results can't be verified — app/Sources/HandsKit/Skills.swift

## Highest-leverage next moves
- brain-3: exclude the done-rejection turn from fail_streak before merging (a one-line flag).
- Premiere: add an expect to each premiere_command (`appears "Export"`), or connect the bridge for add_marker and export_sequence.
- Run test_planner_loop on the Mac (MLX) with one case: fail, fail, then done.
