# ux digest — pass 50

Heads: main 0b83c3b, wip e4f4331, memory-lt 4794e8a, ui-polish e8bceef, brain-9 2590811, decisions ae36620, planner-verify 484f5e7.

Counts: 0 P0, 1 P1, 13 P2. New in pass 50: ux-28.
Open P1:
- ux-28: the failure bubble shows raw harness text, "Not finished: expect failed: …" (orchestrator.py:2689, 1711; on main via planner-verify #54)
Open P2, ranked:
- ux-14: a declined or timed-out confirm leaves the mascot thinking (orchestrator.py)
- ux-25 (ui-polish): the poke hint says "click my mic below" before the 1 s dwell has shown the pill (MascotController.swift)
- ux-27 (memory-lt): the "what do you remember" reply dumps raw rows into the bubble (memory/store.py:244)
- ux-26 (ui-polish): the panel status line says "didn't catch that" for every failure (PanelView.swift)
- ux-19: a grounded-click confirm timeout says "Something went wrong"
- ux-24 (on main): "[" or a backslash forces a confirm on read-only scripts
- ux-17, ux-20, ux-16, ux-18, plus rechecks ux-12, ux-15, ux-22

Highest-leverage next moves:
1. ux-28: in _honest_failure, drop "expect failed:" text so the cleaned _missing_text/fallback copy shows (~0.2 h)
2. ui-polish before merge: on poke, show the pill immediately (ux-25), and fix the confused status copy (ux-26) (~0.3 h)
3. ux-14: ui('idle') after "Okay, cancelled", and reset the mood in onConfirmCancel (~0.25 h)
4. ux-27: add a <=12-word memory bubble renderer before memory-lt merges (~0.3 h)
5. ux-24: lead decision on narrowing the "[" and backslash blocks (~0.5 h)
