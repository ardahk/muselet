
## Your lane: `planner` — System 2: multi-step planning and execution
Files: `prompts/planner_system.md`, the planner loop and DSL executor in `ml/src/brain/` (`orchestrator.py`,
`dsl.py`, and the planner modules as they land), `skills/catalog.json`, and the HandsKit act/verify paths
they call (`app/Sources/HandsKit/Act.swift`, `Observe.swift`). The planner loop is being built now; review
each increment as it appears on `wip/local`/`main`.
Design rules (AGENTS.md): AX tree first, screenshots only when AX is blind; up to 5 actions per batch, each
validated against live AX state, batch stops at the first failed `expect`; DONE is verified by the harness,
never trusted; CONFIRM before irreversible actions; start executing the first parsed action while the planner
is still decoding; localized replanning instead of restarting the task; static prompt prefix cached.
Look hardest at:
- Walk each demo goal through prompt -> DSL -> executor -> HandsKit by hand and report where it breaks:
  (1) "open my downloads as a list", (2) a Safari/Chrome search-and-open flow, (3) Numbers finance:
  categorize transactions, flag duplicates and the ~$1,299 outlier, total by category, list over-budget
  categories (fixtures on `cloud/fixtures-docs`), (4) Premiere: add a marker, cut at playhead, export.
- DSL parse/execute mismatches (prompt says one thing, parser or executor does another), dropped `expect`s,
  `done` without verification, refs used across window changes, pixel-click coordinate conversion.
- Safety: on-screen text treated as instructions (prompt injection), irreversible presses/keys without a
  prior `confirm`, scripts that bypass confirmation.
- Speed: planner calls per task, tokens per call (observation size, prompt cache reuse), streaming execution,
  needless re-observations; estimate wall time per demo goal.
- Recovery: what happens after a failed expect, a stale ref, an app that is not running, a modal dialog.
