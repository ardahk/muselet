# planner lane — pass 2 (wip/local 1d7cc07, main 10793e0, cloud/finance f098120)

## Open P0/P1 (ranked)
1. planner-1 P0 — No planner loop: MULTI_STEP "coming soon"; demo goals 2-4 unreachable — ml/src/brain/orchestrator.py
2. planner-2 P0 — Model can bypass CONFIRM via confirmed=true arg — ml/src/brain/catalog.py, Skills.swift
3. planner-3 P0 — Destructive scripts and press/keys run without confirm — ml/src/brain/orchestrator.py
4. planner-5 P1 — Script ends batch, output discarded, skill/script expects dropped — orchestrator.py
5. planner-4 P1 — Parser rejects `#` comments and ``` fences; prompt example 3 fails — dsl.py
6. planner-9 P1 — Finance engine unreachable from planner/catalog — cloud/finance brain/finance
7. planner-6 P1 — premiere_command unimplemented; catalog vs UXP bridge mismatch — Skills.swift/catalog.json
8. planner-12 P1 — Refs after skill/open/url resolve to previous window — Observe.swift/Act.swift
9. planner-11 P1 — Shell non-zero exit reported ok — Act.swift
10. planner-7 P1 — Pixel click 0-1000 coords not converted — Act.swift
11. planner-8 P1 — Range-formula recipe writes identical formula to every cell — planner_system.md

## Highest-leverage next moves
- Planner loop (planner.py) with per-action results fed back + `done` verified; it's the gate for 3 of 4 demo goals.
- Wire finance via a brain-side `finance_review` skill that runs the cloud/finance engine + trusted scripts; drop rule 8's formula recipe.
- Strip model `confirmed`; label/verb-based gate for press/keys/scripts.
- dsl.parse: skip `#` and fences (10-line fix + test over prompt examples).
- Premiere: brain listens on 8766 for the UXP bridge; razor/undo via keys.
