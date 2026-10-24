# evals-safety digest — pass 41 (2026-10-24T20:22:34Z, main@026aff0)

Open: P0 0, P1 2, P2 10. Resolved this pass: -34. New: -35 (P2).

## Open P0/P1 (ranked)
1. **-25 (P1):** skips are still left out of the live denominator. The document and Finder preconditions skip cases whenever user windows are open.
2. **-11 (P1):** `done` has no harness goal check (4 false_done in 27 live cases).

## Next moves
1. Quote live numbers as passed/executed with skip_reason counts (-25).
2. Triage the 4 false_done traces (-11).
3. Before running planner-demos: add a holdout/v1/live exclusion gate to teachers.py and upload.py, and commit render.py (-35).
4. Run CommsTests and a real Messages compose/decline on the Mac to confirm the -34 wiring.
5. Add the trace-graded caveat (11/43) to REPORT.md and claims.md (-24).
