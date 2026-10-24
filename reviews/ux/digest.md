# ux digest — pass 6 (main d8ad966, wip/local 85ec0df, cloud/brain-2 741465c)

cloud/brain-2 741465c fixes ux-2, ux-3, ux-8, ux-10 and ux-11, plus the brain half of ux-1 (sends confirm_cancel). My confirm and planner-summary tests pass there.
All of these stay open on main and wip until brain-2 merges. Other cloud/* branches have no lane edits of their own.

## Open P0/P1 (ranked)
1. ux-13 App drops new contract frames (confirm_cancel, ui.ms) — app/Sources/MuseletApp/Brain/BrainConnection.swift:252-271
2. ux-1 Confirm timeout leaves app stuck in confirm mode; pendingConfirm also hides every later bubble — BrainConnection.swift, AppDelegate.swift:116,124
3. ux-11 / ux-3 / ux-8 / ux-2 / ux-10 — fixed on cloud/brain-2, open on main until merge — ml/src/brain/orchestrator.py, replies.py
4. ux-4 No ghost/chip for open_app/folder/url/web_search skills (HUD covers only 7 system skills) — HandsKit/RPC.swift, SkillFeedback.swift
5. ux-7 Listening feedback waits on cold AVAudioEngine start — Voice/VoiceController.swift
P2: ux-12 ask/slot-fill shows the listening mascot while the mic is off.

## Highest-leverage next moves
- Merge cloud/brain-2: it closes 5 lane findings at once (copy, errors, confirm naming).
- App: handle confirm_cancel and render the ui.ms latency chip (ux-13, ux-1): ~1 h. The chip is a cheap demo "wow" for speed.
- Key-down: set .listening before recorder.start() and pre-warm the engine at launch (ux-7): ~30 min.
- Add an app-icon chip for open_app/open_folder/open_url (ux-4): ~1 h.
- Ask/slot-fill: use 'thinking' plus a "Hold Right Option to answer" hint instead of 'listening' (ux-12): ~15 min.
