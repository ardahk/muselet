# ux digest — pass 7 (main 4a74659, wip/local 85c73ed)

Big pass. Main merged cloud/brain-2, which resolves ux-2, ux-3, ux-8, ux-10 and ux-11. wip 85c73ed fixes the app side of ux-1 (confirm_cancel), ux-13 (latency chip), ux-4 (ghost flies to Dock icon / menu extra for skills) and ux-7 (listening before engine start, warm engine).
The wip fixes are reviewed statically only. On the Mac, check the new `listen_latency keydown_to_mood_ms` log line and the ghost-to-Dock flight timing.

## Open P0/P1 (ranked)
None open on wip/local. The ux-1/4/7/13 fixes stay open on main until wip lands.

## Open P2
- ux-14 After a confirm timeout, the bubble says "Okay, cancelled" and the mascot stays in thinking ~45 s — ml/src/brain/orchestrator.py:1074-1079
- ux-12 ask/slot-fill shows the listening mascot while the mic is off — orchestrator.py:339,387,525,1072

## Highest-leverage next moves
- Land wip's app changes on main (confirm_cancel, chip, SkillTargets, listening-first).
- ux-14: _end_ui('idle') plus honest timeout copy on the cancel paths: ~15 min.
- ux-12: use 'thinking' plus a "Hold right ⌥ to answer" hint for ask and slot-fill: ~15 min.
- Demo rehearsal on the Mac: confirm the chip shows on skill success (release-to-first-action) and the ghost reaches the Dock within 120 ms.
