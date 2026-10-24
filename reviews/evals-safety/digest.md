# evals-safety digest — pass 44 (2026-10-24T21:08:37Z, main@3876f3a)

Open: P0 0, P1 3, P2 9.

## Open P0/P1 (ranked)
1. **-36 (P1):** 8 planner v2 gold/accept rules pass replies that wipe the field (5 of 130 holdout); unchanged. planner-retrieval's default v2-tune bank would serve 3 of them if k>0.
2. **-25 (P1):** skips and manual cases are left out of the live denominator. Open chat, mail and browser windows still skip cases (now detected via System Events only).
3. **-11 (P1):** `done` has no harness goal check.

## Next moves
1. Fix the 8 v2 rules and add a grader clobber reject. Use the HF bank for any retrieval k>0 (-36).
2. Quote live numbers as passed/executed with skip and manual counts (-25).
3. Triage the 4 false_done traces (-11).
4. Add the trace-graded caveat (11/43) to REPORT.md and claims.md (-24).
