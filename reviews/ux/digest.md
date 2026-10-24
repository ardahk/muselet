# ux digest — pass 42

Heads: main 3772f7c, wip/local 8fcf55f. For lane files, wip/local is identical to main.
Lane code new on main since pass 41 is already-reviewed work landing: the kitten mascot (238db23), the comms-2 routing (c65ee70, plus parser-only ff1a4b6), and clock-timers with the Settings › Timers card and the once-per-session CLOCK_HINT (d060b5a).
The new cloud/*-handoff branches and w9-safety contain handoff notes only. Planner retrieval k=1 is outside this lane.

Counts: 0 P0, 0 P1, 9 P2. None new.
Open P2: ux-14 (confirm-cancel leaves the mascot thinking, orchestrator.py), ux-19 (grounded-click confirm timeout says 'Something went wrong'), ux-17, ux-20, ux-16, ux-18, plus rechecks ux-12, ux-15, ux-22.

Highest-leverage next moves:
1. ux-14: send ui('idle') after every 'Okay, cancelled', and reset the mood in onConfirmCancel (~0.25 h). This is the only stuck-state left on the confirm demo path.
2. ux-19: wrap the two grounded-click ask_confirm calls in try/except RuntimeError, as at 2875 (~0.1 h).
3. ux-17: say the calculator answer before replaying the keys (~0.5 h).
