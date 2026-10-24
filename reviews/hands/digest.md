# hands — digest (pass 19)

Open findings were re-verified on main 2920225 in pass 15: hands-1 to 9 and 11 to 14 are resolved, and hands-15 is superseded.
Pass 19 reviewed wip/local 630d661, which adds about 920 Swift lines:
- Launch skills: open_url, open_folder, Finder view, with a frontmost/title read-back.
- Media keys as `keys volume_up` etc.: NX_SYSDEFINED, tagged as synthetic, focus guard skipped, level read-back.
- Calculator keystroke `type` path, TimerRegistry plus snapshot, and a screen_locked guard.
- verifyFailed errors that carry `result`.
No new defects. RPCs run on rpcQueue, so launch waits (<= 5 s + 3 s) don't block main. cloud/brain-5 only sends `skill` and Finder `keys cmd+1..4` RPCs, which main supports. cloud/decisions has no lane changes.

## Open P0/P1 (ranked)
None.

## Highest-leverage next moves
- hands-16 (P2): when wip/local 630d661 lands, change hobby-gaps' calculator path to a single `type` act (keystroke_app) instead of one `keys` act per character. That saves at least 120 ms of settle per character.
- hands-10 (P2): cap the act ghost-cursor lead in Act.swift (now line 348 on wip/local) with `min(lead, cursor_lead_ms/1000)`.
- Not filed: `appears` still matches substrings and counts other already-open windows of the same app.
