# On-device macOS agent — project guide

## Goal (non-negotiable)
Build the fastest, most accurate, most capable fully on-device macOS computer-use agent.
Beat DeskMind (github.com/deskmind-ai/deskmind) and HobbyLM-1B Computer Use on their own
benchmarks, on this machine, and on public benchmarks. Speed first, then accuracy, then task complexity.
All inference is local (Apple Silicon only). Internet is used only when a task itself needs it.

Hardware target: MacBook Pro M5 Pro, 64 GB, macOS 27. Optimize for MLX / ANE / Metal only.

## Repo layout
- `app/`    Swift package: menu-bar app (voice, mascot, ghost cursor overlay) + `HandsKit` (AX observe/act, native skills, screenshots)
- `ml/`     Python (uv, 3.12): `brain` (orchestrator, model runtime, router, planner, grounder), data, training, evals
- `bench/`  speed lab (`bench/speed_lab.py`)
- `skills/catalog.json`  single source of truth for native skills (read by Swift and Python)
- `evals/`  eval suites + harness
- `data/`, `runs/`, `models/` are gitignored (datasets, logs/traces/results, local weights)

## Architecture
```
push-to-talk -> STT (FluidAudio Parakeet on ANE, streaming partials) -> brain
brain: System 1 decision model (one forward pass -> option probabilities)
         confident -> act  |  unsure / multi-step -> System 2 planner (action batches + expect checks)
       grounder (screenshot -> coords) only when the AX tree is blind
app/HandsKit executes: native skill -> AX action -> keys -> pixel click; verifies via AX state
overlay: mascot + ghost cursor flies to the element frame before acting; TTS reply (Kokoro on ANE)
```
Model lineup is decided by the M0 speed lab (`runs/speedlab/results.jsonl`). Candidates:
System 1 = Qwen3.5-4B decision LoRA (Tinker) vs local 0.8B/0.6B; System 2 = Qwen3.6-35B-A3B vs Qwen3.5-9B/4B;
grounder = Qwen3.5-4B grounding LoRA (Tinker) vs deskmind/eyes-4b vs GUI-Owl-1.5-4B.

## Design rules (evidence-backed; do not drop)
- Model picks, code parses: dates/times via NSDataDetector-style parsing, numbers via parser.
- Every consequential action carries an `expect` predicate; DONE is verified by the harness, never trusted.
- ASK, CONFIRM (send/delete/buy/post/irreversible), REFUSE are explicit actions.
- Decision models train on soft labels (teacher probabilities); no fixed label smoothing. Confidence thresholds are fitted on eval failures.
- Prompt order: static prefix first (cached once, snapshot per request), dynamic state last.
- AX tree is the default observation; screenshots only when AX is insufficient; cap screenshots at ~1 MP and zoom-crop for small targets; never keep old screenshots in history.
- Batch up to 5 actions per planner call; validate each against live AX state before executing; stop the batch at the first failed expect.
- Wait for UI settle (AX notification or 2 stable samples) instead of fixed sleeps.
- Start executing the first parsed action while the planner is still decoding.
- Every live failure becomes a permanent regression test (failure-replay gate).

## Process + protocol
`brain` (Python) runs a WebSocket server on `ws://127.0.0.1:8765`; the app connects as client.
The app owns all TCC permissions (Accessibility, Screen Recording, Microphone, Automation) and executes all OS actions.
One JSON object per frame; `t` = message type.

App -> brain:
- `{"t":"hello","screens":[{"id":1,"frame":[x,y,w,h],"scale":2.0}]}`
- `{"t":"utterance","id":"u1","text":"...","final":false}` (partials allow speculative prefill; `final:true` commits)
- `{"t":"cancel"}`
- `{"t":"rpc_result","id":"r1","ok":true,"result":{...}}` or `{"t":"rpc_result","id":"r1","ok":false,"error":"..."}`
- `{"t":"confirm_reply","id":"c1","yes":true}`

Brain -> app:
- `{"t":"rpc","id":"r1","method":"<observe|act|skill|screenshot|verify|apps>","params":{...}}`
- `{"t":"ui","mascot":"idle|listening|thinking|acting|success|confused|sleeping","bubble":"optional text"}`
- `{"t":"say","text":"..."}`
- `{"t":"confirm","id":"c1","summary":"Send the message to Mom?"}`

RPC methods (HandsKit):
- `observe {scope:"focused_window"|"app"|"menubar", app?, max_nodes:150, diff:true}` ->
  `{epoch, app, window, focused_ref, elements:[{ref,role,label,value?,enabled,frame:[x,y,w,h]}], text, diff_text?, ax_ms}`
  Refs are valid for the returned `epoch`. Frames are global, top-left origin, points.
- `act {op, ref?, text?, combo?, x?, y?, ..., epoch?, expect?}` -> `{ok, error?, act_ms, settle_ms, diff_text?, expect_ok?, observed?}`
  `expect` is sent as the DSL predicate string (e.g. `title~"Downloads"`). Refs are stable across epochs
  while the element persists; `rpc_result` always carries `result` when the handler produced one, even if `ok` is false.
  (fused act-and-observe; the app animates the ghost cursor to the target frame first, `cursor_lead_ms` default 120)
- `skill {name, args}` -> `{ok, result?, error?, ms}`
- `screenshot {window:true, max_pixels:1000000, region?}` -> `{path, width, height, origin:[x,y], scale}` (own windows excluded)
- `verify {expect}` -> `{ok, observed}`
- `apps {}` -> `{running:[...], installed:[...]}`

## Observation text format (what models see)
```
app: Finder | window: "Recents" | focused: #4
#1 button "Back"
#4 textfield "Search" value=""
#7 row "Downloads" selected
```
Diffs: `+ #31 button "Export"`, `- #7`, `~ #4 value="hel"`.

## Action DSL (planner output; one action per line, max 5 per batch)
```
skill <name> key=value ...
press #<ref>
type #<ref> "<text>" [enter]
keys <combo>                      (cmd+shift+n, return, esc)
scroll #<ref> up|down [n]
click <x>,<y> [right|double]      (pixel fallback, only after a screenshot observation)
open "<App Name>"
url "<https://...>"
script applescript|jxa|shell """<code>"""
wait <ms>
ask "<question>"
confirm "<summary>"
done "<summary>"
refuse "<reason>"
expect <predicate>                (applies to the previous action)
  predicates: title~"<text>" | focused #<ref> | value #<ref>="<text>" | app "<name>" | appears "<label>" | gone #<ref>
```

## Decision API (System 1)
`decide(state, questions) -> distributions`. Question kinds: `choice` (<= 26 options, letters A-Z, read as
`choice#<letter>` logits after a prefilled `choice#`), `bool`, `score`. Skills are shortlisted (embedding/BM25 top-K)
before the choice question; special options always present: MULTI_STEP, ASK, REFUSE, ANSWER.
Each question is prefilled on a snapshot of the cached state, so extra questions cost only their own tokens.

## Traces
Every interaction appends JSONL to `runs/traces/`: utterance, observations, model inputs, decisions + probabilities,
actions, results, per-stage latencies, final verification. Traces feed evals, failure replay and training data.

## Commands
- Python env: `uv run --project ml python ...` (deps pinned in `ml/pyproject.toml`)
- Speed lab: `uv run --project ml python bench/speed_lab.py --models <repo...> [--vlm-models <repo...>]`

## Conventions
- Pin dependency versions; prefer releases at least 7 days old.
- No secrets in the repo; API keys only via environment variables (TINKER_API_KEY, HF_TOKEN, OPENAI_API_KEY, ANTHROPIC_API_KEY).
- Licenses: non-commercial datasets (e.g. GUIrilla CC-BY-NC) are allowed for the hackathon build only; track them in `data/LICENSES.md`.
- Never train on eval sets (ScreenSpot-Pro, OSWorld-G, UI-Vision, GUIrilla-Gold, HobbyLM frozen tests, DeskMind Bench, macOSWorld, MacAgentBench); dedupe training data against them.
