# ux digest — pass 14 (full re-verify on main 2920225)

All 13 P1s (ux-1 to ux-11, ux-13) are resolved on main, with file:line evidence in findings.jsonl (pass 14). No branch-only findings remain.
Tests: test_planner_confirm_summary.py 3/3 PASS, and test_confirm_summary_names_object PASS. test_confirm_timeout_clears_app_confirm is stale: its fake ask_confirm doesn't emit confirm_cancel, and the real server.py:174 does.
New merges since bb494af (bench harness #8, split_model, offline planner bench, prompts/) touch no ux-lane files.

## Open P0/P1
None.

## Open P2
- ux-14 After a confirm timeout, the bubble says "Okay, cancelled" and the mascot stays in thinking ~45 s — ml/src/brain/orchestrator.py:716,1320,1383,1423 + AppDelegate.swift:152-160
- ux-15 Automation row shows 'Grant' for already-granted apps that aren't running — Panel/PanelView.swift:297,362 + HandsKit/Automation.swift:85
- ux-12 ask/slot-fill shows the listening mascot while the mic is off — orchestrator.py:525,573,711,1314

## Highest-leverage next moves
- ux-14: set model.mood = .idle in onConfirmCancel, and use "No answer, so I didn't send it." on timeouts: ~15 min.
- ux-15: give .notRunning a neutral chip; the row is complete when nothing is denied or not determined: ~30 min.
- ux-12: use 'thinking' plus a "Hold right ⌥ to answer" hint for ask and slot-fill: ~15 min.
- Planner give-up copy (orchestrator.py:1112): "That didn't work" → "I couldn't finish that. Try smaller steps?": ~5 min.
- Mac rehearsal: read the listen_latency log line and the ghost-to-Dock timing (static review only so far).
