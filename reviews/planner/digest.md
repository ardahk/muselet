# planner lane — pass 12 (main 280715d, wip 38768f3 unchanged; cloud/bench 2c57d7f)

Only cloud/bench moved: a merge of main plus safety guards in the bench cases. Its other differences from main are decision_chunking.py and generic_decide.py, which belong to the router lane, not mine. No change to the open findings.

## Open P1 (ranked)
1. planner-21 P1 — Main brain ignores web_ax_pending; planner plans on half-empty Chrome tree (demo goal 2) — ml/src/brain/orchestrator.py@main
2. planner-20 P1 — Harness's own done-rejection counts toward the 3-failed-turns loop guard — ml/src/brain/orchestrator.py@brain-3 L1080-1105
3. planner-6 P1 — Premiere runs via keyboard shortcuts only; the 8766 UXP bridge isn't connected, so results can't be verified — app/Sources/HandsKit/Skills.swift

## Highest-leverage next moves
- Fix planner-20 on brain-3 (one flag), then merge brain-3. That closes planner-21 too.
- Premiere: add an expect to each premiere_command (`appears "Export"`), or connect the bridge for add_marker and export_sequence.
- Run test_planner_loop on the Mac (MLX) with a fail, fail, done case.
