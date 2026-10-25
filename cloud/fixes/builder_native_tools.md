# Lane: native-tools — "unleash" the 35B with its native tool-calling format (experiment; fast)
Read `cloud/builder_common.md`, `AGENTS.md`, `ml/src/brain/planner.py` (Planner.plan streams our custom DSL with a
line-start OpConstraint, few-shot, done-alone, batch cutting), `ml/src/brain/orchestrator.py::_planner_loop`.
Branch `cloud/native-tools` off latest main, one PR within 90 min, Python only, behind a flag (default OFF; the lead
switches it on for live A/B on the Mac). MLX isn't available here: unit-test with a fake model that returns text.

Hypothesis (user + public evidence: Qwen3.6-35B-A3B ranks #1 among local agent models WITH native tool calls; our
planner forces a custom DSL via constrained decoding + few-shot it was never trained on): letting the 35B use its
native chat-template tool calling, one action per turn (ReAct), with free reasoning, will raise completion on
open-ended app/browser tasks.
Build `NativeToolPlanner` (new module `ml/src/brain/native_planner.py`) with the same `plan(goal, observation,
last_batch, q, loop, **kw)` contract the loop uses (it must put DSL action lines on the queue and return the same info
dict keys: ttft_ms, decode_tok_s, tokens, text...), so `_planner_loop` needs no structural change:
- Render with the model tokenizer's chat template (`tokenizer.apply_chat_template(messages, tools=TOOLS,
  add_generation_prompt=True, enable_thinking=True)`), system prompt = a short agent brief (goal, rules: act on the
  observation, one tool call per turn, never send/buy/delete without `confirm`, call `done` only when the finish
  criterion is visible) + "Finish when:" + app hints; user message = observation text (+ last results, + context block).
- TOOLS (JSON schema): press(ref:int), type(ref:int, text:str, enter:bool=false), keys(combo:str),
  scroll(ref:int, direction:"up"|"down"), open_app(name), open_url(url), click(description:str, double:bool=false),
  wait(ms:int), ask(question), confirm(summary), done(summary), refuse(reason), skill(name, args:object) for system
  skills only.
- Parse Qwen's `<tool_call>{"name":...,"arguments":{...}}</tool_call>` (after `</think>`), map to one DSL line
  (`press #12`, `type #4 "jazz" enter`, `url "..."`, `click "..." double`, `done "..."` ...). Malformed/no tool call ->
  one retry with a short corrective user message, then `ask "I couldn't decide the next step"`.
- Keep history as a compact list of (tool call -> result) lines from `last_batch`/actions log, last 8 turns.
- Thinking: budget 1024 tokens (cap), qwen sampler (T .6, top-p .95, top-k 20); strip think text from history.
- Flag: `--planner-mode dsl|tools` (default dsl), env `PLANNER_MODE` in tools/serve_brain.sh; applies to the main
  planner when PLANNER=35b and to the blind planner. Trace `planner_turn.mode`.
Tests: rendering includes tools; tool-call parsing for each tool incl. quoting/escapes; malformed retry; mapping to DSL
lines the existing executor accepts (`dsl.parse`).
