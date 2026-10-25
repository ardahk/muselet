# ux digest — pass 59

Heads: main 55e38f9, wip fd357b3, design b93bb50, hands-clock 6ab40be, memory a8af560, memory-lt 4794e8a.

Counts: 0 P0, 1 P1, 14 P2. No new findings in passes 52-59; cloud/design resolves ux-26 once merged (ux-25 is still open there) (hands-clock #55 and brain-9 #61 copy OK). New in pass 51: ux-29. ux-25, ux-26 and ux-27 are now live on main (ui-polish #49, memory #58).
Open P1:
- ux-28: the failure bubble shows raw "Not finished: expect failed: …" (orchestrator.py:3061, 2065)
Open P2, ranked:
- ux-29: 512-token thinking on every planner step means a silent "thinking" face of about 2.6 s per step (serve_brain.sh, orchestrator.py:544)
- ux-14: a declined or timed-out confirm leaves the mascot thinking
- ux-25: the poke hint says "click my mic below" before the pill appears (MascotController.swift:189)
- ux-27: the memory recall dumps raw rows into the bubble (memory/store.py:246)
- ux-26: the panel status says "didn't catch that" for every failure (PanelView.swift:242)
- ux-19, ux-24, ux-17, ux-20, ux-16, ux-18, plus rechecks ux-12, ux-15, ux-22

Highest-leverage next moves:
1. ux-28: drop "expect failed:" text in _honest_failure (~0.2 h)
2. ux-29: a per-step progress bubble during planner thinking (~0.3 h); lead to choose THINK_ON / sampler for the demo flows
3. ux-25 + ux-26 + ux-27: copy and pill fixes, now on main (~0.6 h total)
4. ux-14: ui('idle') after "Okay, cancelled", and reset the mood in onConfirmCancel (~0.25 h)
5. ux-24: lead decision on the script gate
