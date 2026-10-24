# Brain lane digest, pass 40 (2026-10-24T20:55Z)

Heads: main dae4b26, wip/local 972081d (main + docs/HANDOFF.md), cloud/planner-demos 9008990, cloud/data-pipeline f6354d6.

Counts (open): P0 0 / P1 8 / P2 10.

Tests: main ml/tests 1347 passed, 2 skipped, 1 deselected (real_model); bench/tests 162 passed, 2 skipped.
Review repros on main: 30 failed / 25 passed (27 older + 3 pass-39 repros, now on main).

## Changes this pass
- brain-35 (P1) and brain-36 (P2) moved to main with the cloud/brain-8 merge (d0c2394). 9a47376 does not change either.
- New brain-37 (P2, cloud/planner-demos): demos lack the router Hint line, blind-AX hint and few-shot block that the runtime sends by default.
- comms 68e76c6 (_preview error bubbles): no finding.
- cloud/data-pipeline f6354d6: route renderer unchanged; teacher --cap only. No finding.

## Top open
1. brain-35 P1 permission gate uses the pre-batch observation (main).
2. brain-25 P1 calculator keys can land in the frontmost app.
3. brain-29 P1 zoom/teams/outlook open websites when apps are installed; failed apps RPC caches [] 60 s.

Other open P1: brain-30, brain-24, brain-16, brain-22, brain-17.
Other open P2: brain-36, brain-37, brain-34, brain-27, brain-28, brain-8, brain-12, brain-14, brain-18, brain-19.
