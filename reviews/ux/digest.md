# ux digest — pass 11 (no lane change since pass 10) / pass 10 (main 280715d, wip/local 38768f3, cloud/brain-3 14a3f52)

Pass 10: main landed it via 894df52 (no other lane changes). Pass 9: wip adds a native Automation onboarding row (per-app chips, Settings… when denied). It's good, but already-granted apps that aren't running show 'Grant' (ux-15).

All P1s are resolved on main: copy and errors via brain-2, plus confirm_cancel, the latency chip, ghost-for-skills and listening-first via 68fa473.
wip 34ddf5f prefetches ghost targets at key-down and skips the Dock read when the Dock auto-hides. Both are good.
brain-3 adds the loop-guard copy ("I'm stuck on that, can you help?") and script timeout/fail copy. All of it is <= 12 words and ends with a final ui.

## Open P0/P1
None.

## Open P2
- ux-15 Automation row shows 'Grant' for already-granted apps that aren't running, so onboarding never shows the green check — Panel/PanelView.swift AutomationChip
- ux-14 After a confirm timeout, the bubble says "Okay, cancelled" and the mascot stays in thinking ~45 s — ml/src/brain/orchestrator.py cancel paths (main 76a03c1, brain-3)
- ux-12 ask/slot-fill shows the listening mascot while the mic is off — orchestrator.py (4 sites)

## Highest-leverage next moves
- ux-15: give .notRunning a neutral chip and count the row as complete when nothing is denied or not determined: ~30 min.
- ux-14: add _end_ui('idle') and "No answer, so I didn't send it." on the timeout paths, or set mood=.idle in onConfirmCancel: ~15 min.
- ux-12: 'thinking' plus a "Hold right ⌥ to answer" hint for ask and slot-fill: ~15 min.
- Mac rehearsal: read `listen_latency keydown_to_mood_ms` and check the ghost reaches the Dock or menu extra before the skill fires. Run once with Dock auto-hide on (no ghost target, which is fine).
- Demo: trigger one deliberate decline ("trash my budget" → "no") to show the named confirm and the clean recovery.
