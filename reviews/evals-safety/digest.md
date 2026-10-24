# evals-safety digest, pass 12 (2026-10-24T08:01:47Z)

## Open P0/P1 (ranked)
No open P0.
1. evals-safety-23 P1: spend guard moved to $120/$140. The level-only latch can skip the $120 warning, and the $140 stop leaves $10 against hours of billing lag (tools/review_pulse.sh, tools/tinker_spend.py)
2. evals-safety-11 P1: done is not harness-verified (ml/src/brain/orchestrator.py)
3. evals-safety-6 P1: destructive-label gating covers only Messages/Mail/Slack, but web AX now feeds page text to the planner (ml/src/brain/orchestrator.py)

Open P2: -8, -12, -17, -20, -21, -22.
Checked, nothing material: tools/tcc_warm.py (127.0.0.1 only, read-only consent scripts). wip AppleScript handler calls (no arg splicing, fixed sources precompiled but not run). ServeSession (headless never auto-confirms). ControlCenter setToggle (Bluetooth is reversible, catalog risk=safe).

## Highest-leverage next moves
- Check/reset runs/tinker_guard.state now. Gate every Tinker job on live spend + estimate <= cap - lag margin (-23).
- Add a harness-side goal check on done (-11).
- Extend label gating to web/Electron chat apps (-6).
- Delete the dead script_needs_confirm and test the real method (-22).
