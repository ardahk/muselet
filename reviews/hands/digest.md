# hands — digest (pass 5, main e78f143 / wip/local e0bdc65; cloud/* touch no app/ product files)

Resolved this pass: hands-2, hands-3, hands-7, hands-11 (all in main e78f143). Earlier: hands-1, 4, 5, 6, 8, 9.

## Open P0/P1 (ranked)
1. hands-12 P1 appears fallback matches menu-bar titles and other windows: false pass — app/Sources/HandsKit/Expect.swift

## Highest-leverage next moves
- hands-12: exclude the menu bar and pre-existing windows from the searchLabel fallback, use word-boundary matching, and run it once at the deadline rather than on every poll.
- hands-10 (P2): read cursor_lead_ms (documented in Act.swift:232, never read); the flight still blocks each act for 120-220 ms.
