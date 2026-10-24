# ux digest — pass 31 (main 5292608, wip a02959b) — all 8 open P2s are on main

All 13 P1s (ux-1 to ux-11, ux-13) are resolved on main, with file:line evidence in findings.jsonl (pass 14). No branch-only findings remain.
Tests: test_planner_confirm_summary.py 3/3 PASS, and test_confirm_summary_names_object PASS. test_confirm_timeout_clears_app_confirm is stale: its fake ask_confirm doesn't emit confirm_cancel, and the real server.py:174 does.
New merges since bb494af (bench harness #8, split_model, offline planner bench, prompts/) touch no ux-lane files.

## Open P0/P1
None.

## Open P2
- ux-14 After a confirm timeout, the bubble says "Okay, cancelled" and the mascot stays in thinking ~45 s — ml/src/brain/orchestrator.py:716,1320,1383,1423 + AppDelegate.swift:152-160
- ux-15 Automation row shows 'Grant' for already-granted apps that aren't running — Panel/PanelView.swift:297,362 + HandsKit/Automation.swift:85
- ux-12 ask/slot-fill shows the listening mascot while the mic is off — orchestrator.py:525,573,711,1314

- ux-16 (now on main) 'a bit brighter' bubble says 'Done'; use result['level'] — replies.py:52 — ml/src/brain/replies.py:48-52
- ux-17 (now on main, partly fixed) Calculator replay: the answer bubble comes only after all keys and the read-back; a mismatch shows a confused face — orchestrator.py _deliver_calc
- ux-18 (now on main) File disambiguation asks 'report.pdf or report.pdf?' — orchestrator.py:611-619
- ux-19 (main :1361,:1419) Grounded-click confirm timeout shows 'Something went wrong' — orchestrator.py _click_target
- ux-20 (now on main) First grounded click cold-loads eyes-4b with no feedback — orchestrator.py _get_grounder

## Highest-leverage next moves
- On main: wrap the ask_confirm in _click_target (ux-19, 5 min); prewarm the grounder for canvas apps and show a 'Looking for X' bubble (ux-20, 30 min).
- On main before rehearsal: ux-16 result-level copy (10 min), ux-18 folder labels (20 min), ux-17 answer-first + keep 'success' on mismatch (15 min).
- ux-14: set model.mood = .idle in onConfirmCancel, and use "No answer, so I didn't send it." on timeouts: ~15 min.
- ux-15: give .notRunning a neutral chip; the row is complete when nothing is denied or not determined: ~30 min.
- ux-12: use 'thinking' plus a "Hold right ⌥ to answer" hint for ask and slot-fill: ~15 min.
- Planner give-up copy (orchestrator.py:1112): "That didn't work" → "I couldn't finish that. Try smaller steps?": ~5 min.
- Mac rehearsal: read the listen_latency log line and the ghost-to-Dock timing (static review only so far).
