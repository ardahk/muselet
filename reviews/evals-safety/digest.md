# evals-safety digest — pass 42 (2026-10-24T20:38:05Z, main@dae4b26)

Open: P0 0, P1 3, P2 9. Resolved this pass: -35. New: -36 (P1).

## Open P0/P1 (ranked)
1. **-36 (P1):** in 8 planner v2 scenarios (5 of 130 holdout), gold/accept rules pass `type #ref "\n..."`, which replaces the whole field (Act.swift:392). The benchmark scores deleting the user's text as correct, and v2-pages-type-save also saves it.
2. **-25 (P1):** skips and now manual cases (ask-text, confirm-no-send) are left out of the live denominator.
3. **-11 (P1):** `done` has no harness goal check.

## Next moves
1. Fix the 8 v2 rules and add a grader clobber reject (as in planner_demos/keep.py), then re-quote holdout-2/v2 (-36).
2. Quote live numbers as passed/executed with skip and manual counts, and run confirm-no-send against a test contact (-25).
3. Triage the 4 false_done traces (-11).
4. Score any planner LoRA trained on planner-demos on v2-holdout only, never v2-tune.
5. Add the trace-graded caveat (11/43) to REPORT.md and claims.md (-24).
