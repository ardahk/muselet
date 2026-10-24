
## Your lane: `brain` — Python orchestrator and on-device decision runtime
Files: `ml/src/brain/*` (server, orchestrator, decision engine, router, planner when it lands, cli,
`vendor/`), `ml/tests/*`, `ml/pyproject.toml`, `bench/speed_lab.py`.
Look hardest at:
- WebSocket server and protocol: conformance with `AGENTS.md` and with the Swift side
  (`app/Sources/MuseletApp/Brain/BrainConnection.swift`, `app/Sources/hands/main.swift`); the receive loop
  must never block on an utterance (RPC results must keep flowing); cancellation of the prior utterance on
  a new final utterance or `cancel`; timeouts that mark executed actions as failed.
- Decision engine token parity with Tinker training: renderer is tinker-cookbook `qwen3_5` with an empty
  `<think>\n\n</think>\n\n` before the `choice#` prefill; ids come from the 58-id alphabet; `choice#` prefix
  tokens are [11409, 2]. Compare against `training/artifacts/route_render_samples.jsonl` (on
  `cloud/data-pipeline` and possibly `wip/local`). Any off-by-one token, BOS/EOS, chat-template or
  whitespace difference silently destroys accuracy — treat it as P0.
- Prompt caching: static prefix cached once and snapshotted per request; Qwen3.5 is hybrid
  (DeltaNet + attention) so recurrent cache state cannot be trimmed — check that cache reuse is exact.
- Argument parsing/normalization (dates, times, durations, levels, deltas): wrong values are worse than ASK.
- Orchestrator safety: `expect` verification, never trusting model DONE, CONFIRM for irreversible actions,
  `script_needs_confirm` regex gaps (shell always confirms).
- Latency: per-stage timings, avoidable round trips, work done after the user stops talking that could be
  done on partials.
Write failing tests in `reviews/brain/tests/` when you find a bug; run the existing suite when possible.
