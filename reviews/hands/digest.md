# hands — digest (pass 1, wip/local b438799; main cdae5d9; cloud/* touch no app/ files)

## Open P0/P1 (ranked)
1. hands-1 P0 Refs reused after window change; act ignores epoch, hits wrong element — app/Sources/HandsKit/Observe.swift
2. hands-2 P0 Voice confirm parser reads 'not right now' / 'ok cancel' as YES — app/Sources/MuseletApp/Voice/VoiceController.swift
3. hands-4 P1 Expect checked once after a 120 ms settle; slow UIs fail falsely — app/Sources/HandsKit/Act.swift
4. hands-3 P1 Agent's own synthesized Esc cancels the running task — app/Sources/MuseletApp/Voice/PushToTalkMonitor.swift
5. hands-8 P1 Synthesized input not bound to the observed app/window — app/Sources/HandsKit/Act.swift
6. hands-5 P1 Screenshot: no region crop, wrong display, arbitrary window picked — app/Sources/HandsKit/Screenshot.swift
7. hands-6 P1 Expect/verify use fixed focused_window cap of 150; gone/appears misjudge — app/Sources/HandsKit/Observe.swift
8. hands-7 P1 Offline utterances replay as commands after reconnect — app/Sources/MuseletApp/Brain/BrainConnection.swift

## Highest-leverage next moves
- Monotonic refs + epoch check in Hands.element (hands-1): smallest change that removes a silent wrong action.
- Harden parseYesNo with negation and ambiguity -> re-ask (hands-2) before any demo of send/delete.
- Poll expect until pass/deadline instead of a single post-settle check (hands-4): fewer false expect_failed, fewer replans.
- Tag synthesized CGEvents and ignore them in the PTT tap (hands-3).
- Not yet filed (next pass): cursor flight up to 220 ms ignores `cursor_lead_ms`; brain protocol.rpc_result drops `result` when ok=false.
