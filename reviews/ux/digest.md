# ux digest — pass 3 (wip/local cbc4879, main dec310b)

No cloud/* branch has lane edits of its own. ux-6 is resolved on wip/local (not yet on main).

## Open P0/P1 (ranked)
1. ux-11 Brain exceptions leave mascot thinking ~45 s, no bubble — ml/src/brain/server.py (new)
2. ux-1 Confirm timeout leaves app stuck in confirm mode — server.py (+AppDelegate/VoiceController)
3. ux-10 Planner confirm shows 'Text Mom: "None"?' — orchestrator.py `_confirm_summary` (new)
4. ux-2 Engine-path confirm never names recipient/file — orchestrator.py `_summary`
5. ux-3 Skill success shows no reply text — orchestrator.py:846
6. ux-4 Ghost cursor never appears for skills — HandsKit/RPC.swift (handsDidRunSkill seam unused)
7. ux-9 Key-down ctx capture blocks main thread before listening — HandsKit/UtteranceCtx.swift
8. ux-5 Offline utterances replay later as surprise actions — BrainConnection.swift
9. ux-8 Failure copy leaks raw skill ids — orchestrator.py:840,845
10. ux-7 Listening feedback waits on cold AVAudioEngine start — VoiceController.swift
P2: ux-12 'ask' shows listening mascot while the mic is off.

## Highest-leverage next moves
- One error/confirm hardening patch: runner except → ui confused + bubble; catch confirm timeout; confirm-done frame (ux-11, ux-1): ~1 h.
- Single `_confirm_summary` for both paths with the body/basename fixes, plus per-skill done text (ux-10, ux-2, ux-3, ux-8): ~1.5 h.
- Key-down path: listening first, mic second, ctx async with a 0.1 s AX timeout (ux-7, ux-9): ~45 min.
- Implement handsDidRunSkill in GhostCursor → chip "Opening Safari…" near the mascot (ux-4): ~1 h.
- Demo polish: success-bubble latency chip from trace release_to_first_action_ms (~45 min).
