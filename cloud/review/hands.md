
## Your lane: `hands` — Swift executor and the Mac app
Files: `app/` (Swift package): `Sources/HandsKit/*` (AX observe/act, stable refs, diffs, skills, scripts,
RPC, screenshots), `Sources/hands/main.swift` (CLI + WebSocket client), `Sources/MuseletApp/*` (menu-bar
app, overlay, ghost cursor, mascot, push-to-talk, STT, permissions, `BrainConnection`), `Tests/*`,
`Package.swift`, `scripts/`.
Look hardest at:
- Protocol conformance with `AGENTS.md` (message types, field names, `rpc_result` always carrying `result`,
  epochs/refs, `expect` predicate DSL and its parser), and agreement with what `ml/src/brain/server.py`
  actually sends/expects.
- AX correctness: stale/stable refs across epochs and window changes, `AXUIElement` lifetime/hash use,
  bounded traversal, frames in global top-left points, multi-display and Retina scale, coordinate
  conversion between CG (top-left) and AppKit (bottom-left) for the ghost cursor and overlays.
- Concurrency: MainActor/AX threading, Swift 6 strict-concurrency holes, blocking calls on the main thread,
  CGEvent tap lifetime and re-enable on timeout, WebSocket reconnect, cancellation.
- Latency: anything that adds avoidable ms to observe/act (redundant AX reads, fixed sleeps instead of settle
  detection, cursor animation blocking the action beyond `cursor_lead_ms`).
- Safety: script/shell confirmation policy, key/mouse synthesis that could act on the wrong window, overlay
  windows being captured in screenshots or intercepting clicks.
- Voice: push-to-talk on Right Option, STT start latency, partial/final utterance framing.
