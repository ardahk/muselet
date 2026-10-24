# ux digest — pass 1 (wip/local bcd3b75, main a5e76fa)

MuseletApp exists only on wip/local; cloud/* doesn't touch this lane.

## Open P0/P1 (ranked)
1. ux-1 Confirm timeout leaves app stuck in confirm mode — ml/src/brain/server.py (+AppDelegate/VoiceController)
2. ux-2 Confirm prompt never names recipient/file — ml/src/brain/orchestrator.py `_summary`
3. ux-3 Skill success shows no reply text — orchestrator.py:375
4. ux-4 Ghost cursor never appears for skills — HandsKit/RPC.swift + GhostCursor.swift
5. ux-6 Utterance frames omit contract ctx — BrainConnection.swift / VoiceController.swift
6. ux-5 Offline utterances replay later as surprise actions — BrainConnection.swift outbox
7. ux-8 Bubble copy leaks raw skill ids, no next step — orchestrator.py
8. ux-7 Listening feedback waits on cold AVAudioEngine start — VoiceController.swift

## Highest-leverage next moves
- Catalog `confirm` + `done` templates per skill (fixes ux-2, ux-3 and half of ux-8): ~1.5 h, biggest perceived-quality jump.
- Confirm lifecycle frame (done/cancel) + app-side 60 s auto-decline (ux-1): ~1 h.
- Ghost cursor for skills: fly to Dock icon / Finder row, or show a chip-only "Opening Safari…" (ux-4): ~2 h.
- Demo polish: latency chip on the success bubble ("0.42 s · on-device") from the release→ui-success time (~45 min). Mascot "offline ✈︎" reaction when ctx.online=false and the task works (~30 min).
- Not yet filed (P2): Reduce Motion ignored (no accessibilityDisplayShouldReduceMotion anywhere). Automation/Calendar/Reminders TCC prompts not in onboarding, so they'll pop mid-demo; add a "Prepare demo" button that triggers each once.
