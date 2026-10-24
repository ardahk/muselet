# ux digest — pass 8 (main 76a03c1, wip/local 34ddf5f, cloud/brain-3 14a3f52)

All P1s are resolved on main: copy and errors via brain-2, plus confirm_cancel, the latency chip, ghost-for-skills and listening-first via 68fa473.
wip 34ddf5f prefetches ghost targets at key-down and skips the Dock read when the Dock auto-hides. Both are good.
brain-3 adds the loop-guard copy ("I'm stuck on that, can you help?") and script timeout/fail copy. All of it is <= 12 words and ends with a final ui.

## Open P0/P1
None.

## Open P2
- ux-14 After a confirm timeout, the bubble says "Okay, cancelled" and the mascot stays in thinking ~45 s — ml/src/brain/orchestrator.py cancel paths (main 76a03c1, brain-3)
- ux-12 ask/slot-fill shows the listening mascot while the mic is off — orchestrator.py (4 sites)

## Highest-leverage next moves
- ux-14: add _end_ui('idle') and "No answer, so I didn't send it." on the timeout paths, or set mood=.idle in onConfirmCancel: ~15 min.
- ux-12: 'thinking' plus a "Hold right ⌥ to answer" hint for ask and slot-fill: ~15 min.
- Mac rehearsal: read `listen_latency keydown_to_mood_ms` and check the ghost reaches the Dock or menu extra before the skill fires. Run once with Dock auto-hide on (no ghost target, which is fine).
- Demo: trigger one deliberate decline ("trash my budget" → "no") to show the named confirm and the clean recovery.
