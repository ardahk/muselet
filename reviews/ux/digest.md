# ux digest — pass 4 + self-poll 2 (wip d5d2d7d, main c2d2988, cloud/brain-2 9f41c11)

No cloud/* branch has lane edits of its own. Resolved: ux-5 (stale offline replay), ux-6 (ctx), ux-9 (ctx capture blocking), all on main too.
Self-poll 1: main 17a2755 merged the System-2 planner loop, so ux-10/11/12 (and ux-1/2/3/8) now affect main as well. cloud/bench and cloud/grounding have no lane edits.
Self-poll 2: cloud/brain-2 9f41c11 fixes ux-2 and ux-10 (shared object-naming _confirm_summary; my tests pass). Merging it is the cheapest win. ux-1 is still stuck there, and a timeout now reads "Okay, cancelled". Slot-fill adds more listening-while-mic-off cases (ux-12).
New since pass 3: SkillHUD (native glass HUD for volume/brightness/dark/Wi-Fi/Bluetooth, honors Reduce Motion) and a timer-done bubble. Good demo polish.

## Open P0/P1 (ranked)
1. ux-11 Brain exceptions leave mascot thinking ~45 s, no bubble — ml/src/brain/server.py:59-66
2. ux-1 Confirm timeout leaves app stuck in confirm mode — server.py:158-168 (+AppDelegate/VoiceController)
3. ux-10 Planner confirm shows 'Text Mom: "None"?' — orchestrator.py `_confirm_summary` (3 failing tests)
4. ux-2 Engine-path confirm never names recipient/file — orchestrator.py `_summary`
5. ux-3 Skill success shows no reply text (outside HUD skills) — orchestrator.py:875
6. ux-4 No ghost/chip for open_app/folder/url/web_search skills — HandsKit/RPC.swift, SkillFeedback.swift
7. ux-8 Failure copy leaks raw skill ids — orchestrator.py:869,874
8. ux-7 Listening feedback waits on cold AVAudioEngine start — VoiceController.swift
P2: ux-12 'ask' shows listening mascot while the mic is off.

## Highest-leverage next moves
- Error/confirm hardening: runner except → ui confused + bubble; catch confirm timeout; confirm-done frame (ux-11, ux-1): ~1 h.
- One shared `_confirm_summary` for both paths (`body`, basename, compose_email/empty_trash) + per-skill done text (ux-10, ux-2, ux-3, ux-8): ~1.5 h.
- Extend SkillFeedback with an app-icon chip for open_app/open_folder/open_url/web_search (ux-4): ~1 h.
- Key-down: set .listening before recorder.start(); prepare the engine once at launch (ux-7): ~30 min.
- Demo polish: success-bubble latency chip from release_to_first_action_ms (~45 min).
