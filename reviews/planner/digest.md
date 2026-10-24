# planner lane — pass 3 (wip/local cbc4879, main dec310b)

Resolved this pass: planner-2, -3, -5, -7, -12; planner-1 superseded by the new planner loop.

## Open P0/P1 (ranked)
1. planner-14 P1 — Script body lines counted as actions; decode cut at 5 lines/220 tok — ml/src/brain/planner.py
2. planner-13 P1 — `done` accepted without harness verification — ml/src/brain/orchestrator.py
3. planner-9 P1 — finance_review in catalog but no tools module -> "almost ready" — ml/src/brain/tools/
4. planner-15 P1 — Script policy confirms nearly every Numbers script — orchestrator.py
5. planner-16 P1 — Script output truncated to 300 chars — orchestrator.py / planner.py
6. planner-4 P1 — ``` fence lines fail the batch — orchestrator.py/dsl.py
7. planner-6 P1 — Premiere via keys only; bridge unconnected, results unverifiable — Skills.swift
8. planner-11 P1 — Shell non-zero exit reported ok — Act.swift
9. planner-8 P1 — Range-formula recipe writes identical formula to every cell — planner_system.md

## Highest-leverage next moves
- Fix in_script line counting in planner.plan (one flag) before any Numbers demo run.
- Land tools/finance_review.py on the cloud/finance engine with trusted scripts (also fixes planner-10/15/16 for the demo).
- Verify `done` against the last passed expect.
- Skip ``` lines in _planner_loop next to the `#` skip.
- Speed: every turn re-observes and sends the full obs text (not diff) — ~2-3k tok prefill/turn on top of the cached system prefix.
