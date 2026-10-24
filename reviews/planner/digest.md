# planner lane — pass 1 (wip/local bcd3b75, main a5e76fa)

## Open P0/P1 (ranked)
1. planner-1 P0 — No planner loop: MULTI_STEP says "coming soon"; demo goals 2-4 unreachable — ml/src/brain/orchestrator.py
2. planner-2 P0 — Model can bypass CONFIRM by emitting confirmed=true — ml/src/brain/catalog.py, Skills.swift
3. planner-3 P0 — Destructive scripts and press/keys run without confirm — ml/src/brain/orchestrator.py
4. planner-4 P1 — Parser rejects `#` comments and ``` fences; prompt example 3 fails — ml/src/brain/dsl.py
5. planner-5 P1 — Script ends batch, script output discarded, skill/script expects dropped — ml/src/brain/orchestrator.py
6. planner-6 P1 — premiere_command unimplemented; catalog args mismatch UXP bridge — Skills.swift / catalog.json
7. planner-7 P1 — Pixel click uses 0-1000 image coords as global points — Act.swift
8. planner-8 P1 — Numbers range-formula recipe writes identical formula to every cell — planner_system.md

## Highest-leverage next moves
- Build planner.py loop that feeds per-action results (script output, expect observed, errors) back; verify `done` via `verify` before success.
- Strip model-supplied `confirmed`; gate press/keys/scripts by destructive label/verb before any demo with Mail/Messages/Finder.
- Fix dsl.parse for `#` and fences; add a test parsing every prompt example.
- Queued for pass 2: shell rc!=0 returns ok (Act.swift L412-416); refs after a skill RPC point at the previous window (no re-observe; element() ignores epoch); `open` returns before the app is key and settles on the old pid -> race with next keys.
- Speed: prompt prefix ~4.8k chars (~1.2k tok) + catalog; 150-node obs ~2-3k tok/turn; expect 3-6 planner calls for goals 2-4 (~1.5-3 s each on 35B-A3B) -> 6-15 s per goal if the cache prefix is reused.
