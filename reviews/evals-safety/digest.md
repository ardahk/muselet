# evals-safety digest, pass 21 (2026-10-24T10:03:11Z): main 758a017 unchanged; reviewed wip/local 630d661, cloud/decisions c08a96d, cloud/brain-5 003d1bb, nothing material

## Open P0/P1 (ranked)
No open P0.
1. evals-safety-25 P1: the document guard skips 9/43 live cases (plus time-event if the calendar probe fails) and drops them from the denominator (bench/harness/documents.py, bench/live/run_live.py)
2. evals-safety-6 P1: Enter/Send in Discord/WhatsApp/web composers is unconfirmed (ml/src/brain/orchestrator.py)
3. evals-safety-11 P1: done is accepted after an expect-less batch + fresh observe (ml/src/brain/orchestrator.py:1076-1093)
4. evals-safety-23 P1: the spend guard's level-only latch and $10 margin (tools/review_pulse.sh:25-31)
5. evals-safety-26 P1 (cloud/data-pipeline): main-final's training rows have no decontam record (training/src/muselet_train/datums_export.py)

Resolved this pass: -29 (hobby-gaps ef95140: calc before the router only in Calculator context). Open P2: -8, -12, -20, -21, -22, -24, -28.
Pass 21 checked, nothing material: brain-5 pathfind (a single resolved path for move_to_trash still goes through confirm, which now shows the full path); decisions decontam (fails closed if the JevBench/Typed-Decisions references are missing); wip keystroke typing for Calculator. Earlier: the brain-4 escalate planner (opt-in, same done gate); the pitch-2 claims re-verify (-2 resolved, -11 partial: both correct).

## Highest-leverage next moves
- Scope the doc guard to the case's own apps, and print skipped alongside passed/executed (-25).
- Confirm `type ... enter` in any chat-like composer (-6). Require a passed expect before done (-11).
- Export main's rows with --reader dedup and decontam them (-26).
- Fix the guard latch, and cap tokens in the Tinker bench backend (-23, -28).
- Qualify claims.md:66: 12/43 live cases are trace-graded (-24).
