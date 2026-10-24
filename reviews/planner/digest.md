# planner lane — pass 7 (main d8ad966, wip 85ec0df, cloud/brain-2 741465c, cloud/finance-2 dfaf785)

Resolved: planner-8 on main. planner-4, -13, -16 and -18 are fixed on cloud/brain-2, but main and wip only get those fixes once brain-2 is merged.
wip 85ec0df WebAX (Safari AXEnhancedUserInterface + Chromium manual AX, 0.3 s populate wait) reviewed. It helps demo goal 2, and I found no issues.

## Open P1 (ranked)
1. planner-9 P1 — finance_review exists only on cloud/finance-2. Main and wip still fall back — ml/src/brain/tools/
2. planner-6 P1 — Premiere runs via keyboard shortcuts only; the UXP bridge isn't connected, so results can't be verified — Skills.swift
3. planner-11 P1 — A shell script that exits non-zero is reported ok — Act.swift
(On main and wip, planner-4/13/16/18 stay open until brain-2 is merged.)

## Highest-leverage next moves
- Merge cloud/brain-2 (fixes 4 planner findings in one step) and then cloud/finance-2 (finance demo).
- Premiere: connect the 8766 UXP bridge for add_marker/export so the result can be verified, or add an expect via the window title / Export dialog.
- Act.swift: set ok=false when a shell script exits non-zero.
