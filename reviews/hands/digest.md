# hands — digest (pass 5 + self-polls to 07:02Z: main c2d2988, wip/local d5d2d7d, cloud/brain-2 9f41c11)

Resolved in pass 5: hands-2, hands-3, hands-7, hands-11 (main e78f143). Earlier: hands-1, 4, 5, 6, 8, 9.

## Open P0/P1 (ranked)
1. hands-13 P1 Act never reports truncated, so brain-2 diff reuse drops capped elements — app/Sources/HandsKit/Act.swift (consumer: cloud/brain-2 ml/src/brain/orchestrator.py)
2. hands-12 P1 appears fallback matches menu-bar titles and other windows: false pass — app/Sources/HandsKit/Expect.swift

## Highest-leverage next moves
- hands-13: set `truncated` on act results (sticky across expect polls, like sawFull) before brain-2 merges. Otherwise the planner loses elements in large windows.
- hands-12: exclude the menu bar and pre-existing windows from the searchLabel fallback, use word-boundary matching, and run it once at the deadline rather than on every poll.
- hands-10 (P2): read cursor_lead_ms (documented in Act.swift:232, never read); the flight still blocks each act for 120-220 ms.
