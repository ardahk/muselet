# ux digest — pass 2 (wip/local 1d7cc07, main 10793e0)

The app has landed on main (6d3d0e9); findings apply to main and wip/local. No cloud/* branch has lane edits of its own.
Resolved on wip/local: ux-6 (utterance ctx).

## Open P0/P1 (ranked)
1. ux-1 Confirm timeout leaves app stuck in confirm mode — ml/src/brain/server.py (+AppDelegate/VoiceController)
2. ux-2 Confirm prompt never names recipient/file — ml/src/brain/orchestrator.py `_summary`
3. ux-3 Skill success shows no reply text — orchestrator.py:427
4. ux-4 Ghost cursor never appears for skills — HandsKit/RPC.swift + GhostCursor.swift
5. ux-9 Key-down ctx capture blocks main thread before listening — HandsKit/UtteranceCtx.swift (new)
6. ux-5 Offline utterances replay later as surprise actions — BrainConnection.swift outbox
7. ux-8 Bubble copy leaks raw skill ids, no next step — orchestrator.py (partly fixed)
8. ux-7 Listening feedback waits on cold AVAudioEngine start — VoiceController.swift

## Highest-leverage next moves
- Catalog `confirm` + `done` templates per skill (ux-2, ux-3, rest of ux-8): ~1.5 h, biggest perceived-quality jump.
- Confirm lifecycle frame (done/cancel) + app-side auto-decline (ux-1): ~1 h.
- Key-down path: set listening first, then start the mic, then capture ctx async with a 0.1 s AX timeout (ux-7 + ux-9): ~45 min.
- Ghost cursor for skills: Dock/Finder target or a chip-only "Opening Safari…" (ux-4): ~2 h.
- Demo polish: latency chip on the success bubble ("0.42 s · on-device") ~45 min; "offline ✈︎" reaction when ctx.online=false ~30 min (ctx.online is now available).
