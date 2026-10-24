# evals-safety digest — pass 43 (2026-10-24T20:53:00Z, main@27ebd13)

Open: P0 0, P1 3, P2 9.

## Open P0/P1 (ranked)
1. **-36 (P1):** 8 planner v2 gold/accept rules pass replies that wipe the field (5 of 130 holdout). planner-retrieval's default v2-tune bank would also serve 3 such golds as live few-shot examples if k>0.
2. **-25 (P1):** skips and manual cases are left out of the live denominator.
3. **-11 (P1):** `done` has no harness goal check.

## Next moves
1. Fix the 8 v2 rules and add a grader clobber reject. Until then, use the HF clobber-filtered bank for any retrieval k>0 (-36).
2. Quote live numbers as passed/executed with skip and manual counts (-25).
3. Triage the 4 false_done traces (-11).
4. Add the trace-graded caveat (11/43) to REPORT.md and claims.md (-24).
