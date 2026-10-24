# evals-safety digest, pass 23 (2026-10-24T10:33:28Z): main d514300 (brain-4 merged, serve_brain.sh defaults)

## Open P0/P1 (ranked)
No open P0.
1. evals-safety-25 P1: the document guard skips 9/43 live cases (plus time-event if the calendar probe fails) and drops them from the denominator (bench/harness/documents.py, bench/live/run_live.py)
2. evals-safety-6 P1: Enter/Send in Discord/WhatsApp/web composers is unconfirmed (ml/src/brain/orchestrator.py)
3. evals-safety-11 P1: done is accepted after an expect-less batch + fresh observe (ml/src/brain/orchestrator.py:1076-1093)
4. evals-safety-23 P1: the spend guard's level-only latch and $10 margin (tools/review_pulse.sh:25-31)
5. evals-safety-26 P1 (now main: serve_brain.sh defaults to main-final, picked on route_v1): main-final's training rows have no decontam record (training/src/muselet_train/datums_export.py)

Resolved this pass: -29 (hobby-gaps ef95140: calc before the router only in Calculator context). Open P2: -8, -12, -20, -21, -22, -24, -28.
Pass 21 checked, nothing material: brain-5 pathfind (a single resolved path for move_to_trash still goes through confirm, which now shows the full path); decisions decontam (fails closed if the JevBench/Typed-Decisions references are missing); wip keystroke typing for Calculator. Earlier: the brain-4 escalate planner (opt-in, same done gate); the pitch-2 claims re-verify (-2 resolved, -11 partial: both correct).

## Highest-leverage next moves
- Scope the doc guard to the case's own apps, and print skipped alongside passed/executed (-25).
- Confirm `type ... enter` in any chat-like composer (-6). Require a passed expect before done (-11).
- Export main's rows with --reader dedup and decontam them (-26).
- Fix the guard latch, and cap tokens in the Tinker bench backend (-23, -28).
- Qualify claims.md:66: 12/43 live cases are trace-graded (-24).


Pass 25 (main 26ff05b, wip 2c79363, data-pipeline eae3b7e, decisions 91a62c2, hobby-gaps 861b991): no new findings. brain-5 merge + argfix kill/cut=off verified (mute polarity kept). it2 H9 ARGS gate is on val ARGS (ok). decisions teacher gate goes through BudgetLedger (ok). All open P1s unchanged.

Pass 25 (main d502b78, wip c7c04ce, data-pipeline 19737e1, decisions 6d395df, hobby-gaps 156556e): no new findings. -26 narrowed: the decontam record exists and confirms 37/140 route_v1 + 10/43 live_t1 near-dups in main-final training. route_v1_clean (103) is on main but unused; no live_t1 clean subset; serve_brain cites full-set r2 1.000. The it2 train.py hard gate (aborts before spend) looks right. decisions amendment 3 caps cumulative generation spend at $57. -6/-11/-23/-25 unchanged.
