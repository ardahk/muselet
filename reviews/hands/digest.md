# hands — digest (pass 7: main d8ad966, wip/local 85ec0df, cloud/brain-2 741465c, cloud/grounding 3441ee8)

Resolved: hands-1, 2, 3, 4, 5, 6, 7, 8, 9, 11.

## Open P0/P1 (ranked)
1. hands-14 P1 App ignores confirm_cancel, so a stale confirm swallows the next commands — app/Sources/MuseletApp/Brain/BrainConnection.swift
2. hands-12 P1 appears fallback matches menu-bar titles and other windows: false pass — app/Sources/HandsKit/Expect.swift

## Highest-leverage next moves
- hands-14: handle `confirm_cancel` (clear pendingConfirm, hide the bubble) and pass `ui.ms` to the latency chip. Both are new contract frames from main d8ad966 that the app drops.
- hands-12: exclude the menu bar and pre-existing windows from the searchLabel fallback, use word-boundary matching, and run it once at the deadline.
- hands-13 (P2): set `truncated` on act results (sticky across polls) so brain-2's diff reuse is safe in every case.
- hands-15 (P2): record web AX as enabled only if setAttr succeeded, so Chrome isn't left AX-blind after a fast open+observe.
- hands-10 (P2): honour cursor_lead_ms; the ghost-cursor flight still blocks each act for 120-220 ms.
