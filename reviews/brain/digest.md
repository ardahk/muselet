# Brain lane review: pass 82 (2026-10-25T08:55Z)

Open: P0 0, P1 14, P2 25. New: brain-68 (P1).

## Branches
- main b7b38f9: merged agentic-fixes2 104a411 and docs-final. ab850b3 adds soft expects and a 30-turn / 300 s budget for blind tasks; b7b38f9 adds MUSELET_OBS_NODES (350 with PLANNER=35b).
- wip/local e03e2c8: snapshot on main; lane identical.

## New
- brain-68 (P1, main): on blind/agentic tasks a failed planner expect skips the loop guard. Repro test_brain_pass82.py: a repeated failing `type` runs 30 times on main and stops after 2 on 104a411.

## Rechecked
- brain-66 and brain-67 now on main; brain-65 still on main.
- brain-60 is wider on main: subject-free YouTube evidence, and auto-done is accepted with verify off.
- All other open findings unchanged.

## Tests
main: 18 MLX-only suite failures (2476 passed, 110 skipped). Review repros: 62 failed, 53 passed.
