# hands — digest (pass 4, wip/local cbc4879; main dec310b; cloud/* touch no app/ files)

Resolved this pass: hands-1, hands-4, hands-5, hands-6, hands-8.

## Open P0/P1 (ranked)
1. hands-2 P0 Voice confirm parser reads 'not right now' / 'ok cancel' as YES — app/Sources/MuseletApp/Voice/VoiceController.swift (now also gates the new empty_trash skill)
2. hands-12 P1 appears fallback matches menu-bar titles and other windows: false pass — app/Sources/HandsKit/Expect.swift
3. hands-3 P1 Agent's own synthesized Esc cancels the running task — app/Sources/MuseletApp/Voice/PushToTalkMonitor.swift (tagging landed; tap filter missing)
4. hands-11 P1 Ctx capture runs on main thread with 6 s AX default timeouts — app/Sources/HandsKit/UtteranceCtx.swift
5. hands-7 P1 Offline utterances replay as commands after reconnect — app/Sources/MuseletApp/Brain/BrainConnection.swift

## Highest-leverage next moves
- hands-2: negation/ambiguity-aware parseYesNo before demoing send/delete/empty_trash.
- hands-3: one line in the PTT tap: ignore SyntheticEvent.isTagged events.
- hands-12: exclude the menu bar and pre-existing windows from the appears fallback, and use word-boundary matching.
- hands-11: 50 ms AX timeouts in UtteranceCtx, and run it off the main thread.
- hands-10 (P2): honor cursor_lead_ms (only documented in Act.swift:232, never read).
