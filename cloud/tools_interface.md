# Brain tool interface (for `executor: "brain"` skills)

Catalog skills marked `"executor": "brain"` (`finance_review`, `advisor_prep`) are not executed by HandsKit. After
the router picks one and ARGS extraction + typed coercion run, the orchestrator calls
`await brain.tools.run(orch, name, args, utterance)`, which lazily imports `brain.tools.<name>` and calls:

```python
async def run(orch, args: dict, utterance: str) -> str:   # outcome: ok|failed|awaiting_user|cancelled|fallback
```

The registry `ml/src/brain/tools/__init__.py` is owned by the brain agent; tool authors add only their own module
`ml/src/brain/tools/<name>.py` and tests `ml/tests/test_tool_<name>.py`.

What a tool may use (all async):
- `await orch.server.rpc(method, params, timeout=30) -> dict` — HandsKit RPCs from AGENTS.md. Raises RuntimeError on
  timeout/disconnect. Results carry `ok`. Useful calls:
  - `rpc("act", {"op": "script", "lang": "applescript", "code": src})` -> `{ok, output | error}` (tool-generated
    scripts are trusted code: they bypass the planner's script-confirmation policy, so never interpolate unescaped
    user/model text into them).
  - `rpc("skill", {"name": "open_file" | "open_folder" | "open_app" | ..., "args": {...}})` -> `{ok, result?, error?}`
    (visible steps: the app animates the ghost cursor and brings the app forward).
  - `rpc("ocr", {"path": "/abs/file.png"})` -> `{text, lines:[{text, frame}], ms}` (Apple Vision, on device).
  - `rpc("observe", {"scope": "focused_window", "max_nodes": 150})` -> observation (see AGENTS.md).
- `await orch.server.say(text)` — speech-bubble text, <= 12 words, no audio.
- `await orch.server.ui(mood, bubble=None)` — moods: idle|listening|thinking|acting|success|confused|sleeping.
- `await orch.server.ask_confirm(summary) -> bool` — required before anything irreversible or external.
- `orch.tracer.stage(name, ms)` — per-stage latency in the trace.

Rules:
- Deterministic code computes every number; the LLM never does arithmetic. Every claim shown to the user carries
  evidence (rows/lots + rule) in the trace and, where it fits, in the written output.
- Visible choreography for the demo: bring each app forward as you use it (Calendar, Finder, Numbers, Notes) and
  update the bubble at each step ("Reading the Hendersons' portfolio..."). Target <= 30 s wall time end to end;
  run independent reads concurrently; never sleep for fixed times except a <= 300 ms pause after bringing an app
  forward so the viewer sees it.
- Cancellation: tools must let `asyncio.CancelledError` propagate (the user can say "stop" at any time).
- Failure: on any RPC error return "failed" after `say`-ing a short, specific reason ("Couldn't read the budget
  sheet"); raw errors go to the trace.
- Tests run on Linux with a fake `orch` (record RPC calls, return canned results): assert the RPC sequence, the
  generated scripts (golden), the bubble texts, and the outcome. Run with `PYTHONPATH=ml/src python -m pytest`.
