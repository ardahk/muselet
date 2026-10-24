# ux digest — pass 44

Heads: main ebdd639 / wip eb1d232 (briefs only), ui-polish e8bceef, w9-safety 2a7d0df, memory 5cd44e6.

Counts: 0 P0, 0 P1, 12 P2. Two new: ux-25, ux-26.
Open P2, ranked:
- ux-14: a declined or timed-out confirm leaves the mascot thinking (orchestrator.py)
- ux-25 (ui-polish): the poke hint says 'click my mic below' before the 1 s dwell has shown the pill (MascotController.swift)
- ux-26 (ui-polish): the panel status line says 'didn't catch that' for every failure (PanelView.swift)
- ux-19: a grounded-click confirm timeout says 'Something went wrong'
- ux-24 (w9-safety): '[' or a backslash forces a confirm on read-only scripts
- ux-17, ux-20, ux-16, ux-18, plus rechecks ux-12, ux-15, ux-22

Highest-leverage next moves:
1. ui-polish before merge: on poke, show the pill immediately (ux-25), and fix the confused status copy (ux-26) (~0.3 h)
2. ux-14: ui('idle') after 'Okay, cancelled', and reset the mood in onConfirmCancel (~0.25 h)
3. ux-24: narrow the '[' and backslash blocks before merging w9-safety (~0.5 h)
