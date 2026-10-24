# planner lane — pass 8 (main 4a74659 = brain-2 + finance-2 + advisor-2 + grounding + pitch merged; wip 85c73ed)

Resolved: planner-4, -9, -13, -16 and -18 are now on main, and planner-11 is fixed on wip.
Non-MLX tests on main: 224 passed (dsl, orchestrator, catalog, finance, tool_finance_review). test_planner_loop needs mlx, so I couldn't run it on Linux.
wip 85c73ed changes reviewed with no issues: the Expect `appears` no longer matches menu-bar items, shell timeout/exit handling, and the truncated flag that breaks the diff chain.

## Open P1
1. planner-6 P1 — Premiere runs via keyboard shortcuts only. The UXP bridge (8766) isn't connected, so marker/razor/export results can't be verified — app/Sources/HandsKit/Skills.swift

## Highest-leverage next moves
- Premiere demo: give each premiere_command an expect (the Export dialog `appears "Export"`, a marker panel count). Alternatively, connect the bridge's add_marker/export_sequence so the result can be verified.
- Run test_planner_loop on the Mac (needs MLX) before the demo. It covers the streaming/done/fallback paths I could only check by reading the code.
