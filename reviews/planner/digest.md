# planner lane — pass 4 (wip/local e0bdc65, main e78f143)

Resolved this pass: planner-14 (script line counting), -15 (Numbers over-confirm), -17 (double confirm), -10 (on cloud/finance-2).

## Open P0/P1 (ranked)
1. planner-9 P1 — finance_review tool only on cloud/finance-2; wip/main still fall back — ml/src/brain/tools/
2. planner-18 P1 — Brain-tool fallback in planner loop repeats 'almost ready' up to 12 turns — orchestrator.py
3. planner-19 P1 — A line that fails to parse no longer stops the batch — orchestrator.py
4. planner-13 P1 — `done` still unverified (second alone-done accepted) — orchestrator.py
5. planner-16 P1 — Script output capped at 300 chars vs prompt rule 8 reading 121 rows — orchestrator.py/planner.py
6. planner-4 P1 — ``` fence lines fail (now feeding planner-19) — orchestrator.py/dsl.py
7. planner-6 P1 — Premiere via keys only; bridge unconnected — Skills.swift
8. planner-11 P1 — Shell non-zero exit reported ok — Act.swift
9. planner-8 P1 — Range-formula recipe identical formula per cell — planner_system.md

## Highest-leverage next moves
- Merge cloud/finance-2 tools/finance_review.py, and make a brain-tool result terminal in _planner_loop.
- Restore failed=True/cancel.set() on parse errors; skip ``` lines.
- Gate `done` on the last passed expect (or re-observe and diff) instead of 'say it twice'.
- Lift script output cap to ~4k or tell rule 8 to read small ranges only.
