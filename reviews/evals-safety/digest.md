# evals-safety digest, pass 13 (2026-10-24T08:17:18Z)

## Open P0/P1 (ranked)
No open P0.
1. evals-safety-23 P1: spend guard at $120/$140. The level-only latch can skip the $120 warning, and the $140 stop leaves $10 against hours of billing lag (tools/review_pulse.sh, tools/tinker_spend.py)
2. evals-safety-11 P1: done is not harness-verified (ml/src/brain/orchestrator.py)
3. evals-safety-6 P1: destructive-label gating covers only Messages/Mail/Slack, but web AX feeds page text to the planner (ml/src/brain/orchestrator.py)

Open P2: -8, -12, -17, -20, -21, -22, -24 (8/43 live cases trace-graded while pitch says final state).
Checked, nothing material: data-pipeline eval_route.py (route_v1 yes/no ctx strings -> bool for the 4 string-valued cases; the label is one-hot on the committed label; val split only). mlx_parity field rename. live_t1 teardowns now close only never-saved docs, and bench/live run_live.py + harness core.py:343-351 enforce precondition -> skipped mechanically. HandsKit no_text_target guard.

## Highest-leverage next moves
- Check/reset runs/tinker_guard.state. Gate every Tinker job on live spend + estimate <= cap - lag margin (-23).
- Add a harness-side goal check on done (-11).
- Extend label gating to web/Electron chat apps (-6).
- Split trace-graded live cases out of the headline pass rate, or add readbacks (-24).
- Delete the dead script_needs_confirm and test the real method (-22).
