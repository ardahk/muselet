# ux digest — pass 69

Heads: main e425cad, wip 80c871c, design-polish bf4ae64, hands-clock 6ab40be, memory a8af560, memory-lt 4794e8a.

Counts: 0 P0, 1 P1, 13 P2 (ux-29 resolved: the LoRA planner defaults to THINK=0). New in pass 63: ux-30 (fix-pending: speech that isn't a command during a confirm gets no feedback). ux-26 resolved by design #70 (main e425cad); ux-25 and ux-27 still live on main.
Open P1:
- ux-28: the failure bubble shows raw "Not finished: expect failed: …" (orchestrator.py:3061, 2065)
Open P2, ranked:
- ux-14: a declined or timed-out confirm leaves the mascot thinking
- ux-25: the poke hint says "click my mic below" before the pill appears (MascotController.swift:210)
- ux-27: the memory recall dumps raw rows into the bubble (memory/store.py:246)
- ux-19, ux-24, ux-17, ux-20, ux-16, ux-18, plus rechecks ux-12, ux-15, ux-22

Highest-leverage next moves:
1. ux-28: drop "expect failed:" text in _honest_failure (~0.2 h)
2. ux-29: a per-step progress bubble during planner thinking (~0.3 h); lead to choose THINK_ON / sampler for the demo flows
3. ux-25 + ux-27: poke hint/pill and memory bubble copy, on main (~0.5 h total)
4. ux-14: ui('idle') after "Okay, cancelled", and reset the mood in onConfirmCancel (~0.25 h)
5. ux-24: lead decision on the script gate
