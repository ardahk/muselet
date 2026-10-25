# ux digest — pass 81

Heads: main b7b38f9, wip e03e2c8, design-polish bf4ae64, hands-clock 6ab40be, memory a8af560, memory-lt 4794e8a.

Counts: 0 P0, 2 P1, 15 P2 (ux-29 reopened, now on main: blind planner thinks 512 tokens every turn) (ux-29 resolved: the LoRA planner defaults to THINK=0). New in pass 63: ux-30 (fix-pending: speech that isn't a command during a confirm gets no feedback). ux-26 resolved by design #70 (main b7b38f9); ux-25 and ux-27 still live on main.
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

- ux-31 (P2, now on main b7b38f9, AGENTIC_APPS=1 default): agentic-apps defaults on, so all 12 app skills (timer, message, email, notes, music, Premiere) run through the multi-turn planner with only 'thinking'. Lead decision: default off, or only after the native skill fails.

- ux-29 update (main b7b38f9): the blind planner now defaults to the 35B whenever its weights are cached, still with 512 thinking tokens every turn. Measure Spotify and timer turn_ms, then decide the default.

- ux-31 now P1 (main b7b38f9): timer, reminder and email demo beats plan on the 35B with 512 thinking tokens, with no bubble. Rehearse beats 3-4 with turn_ms logged and decide.
- ux-32 (P2, docs-final): the demo script claims 4B LoRA ~0.3 s/step for app tasks, which no longer matches main.


## Pass 81 additions
- ux-33 (P2): agentic loop may run 300 s / 30 turns with only 'thinking' visible; add per-turn progress bubble and a 'Keep going?' check at ~30-45 s.
- ux-32 now on main: fix demo_script.md:53 planner/latency claim before recording.
