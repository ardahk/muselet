# On-device macOS agent — project guide

## Goal (non-negotiable)
Build the fastest, most accurate, most capable fully on-device macOS computer-use agent.
Beat DeskMind (github.com/deskmind-ai/deskmind) and HobbyLM-1B Computer Use on their own
benchmarks, on this machine, and on public benchmarks. Speed first, then accuracy, then task complexity.
All inference is local (Apple Silicon only). Internet is used only when a task itself needs it.

Hardware target: MacBook Pro M5 Pro, 64 GB, macOS 27. Optimize for MLX / ANE / Metal only.

Product decisions: voice input only (push-to-talk, Right Option). No text-to-speech: the mascot replies
with short text (<= 12 words) in a speech bubble. Demo covers macOS system tasks, browser (Chrome/Safari),
spreadsheet finance (Numbers / Google Sheets), Premiere Pro, plus 1-2 "wow" moments.
Hackathon deadline: Cal Hacks submission Sun Oct 25 2026, 09:00 PDT. Tinker budget: $150 hard cap.

## Standing decisions from the user (Sat Oct 24)
- Before declaring any model/config "better" (router, planner, grounder, quantization), tune the tweakable knobs
  of EACH option fairly first (prompt/format, decoding, thresholds, cache use, quantization, image size/zoom, LR/epochs)
  and compare tuned vs tuned, with the numbers and settings recorded. Every knob change starts from research
  (model cards, papers, upstream code, our traces) and a written hypothesis with the reasoning; record whether the
  result confirmed or refuted it.
- LIVE-TEST SAFETY (after an incident: a manual E2E typed into a user's open TextEdit document outside this project,
  and autosave wrote it to disk): live UI cases run only through a runner that enforces each case's `precondition`
  mechanically, never by hand; a failed precondition means SKIP. Agents never type into, edit, save or close
  documents/windows they did not create in the same case, and never interact with apps that have user documents
  open unless the case created them. Live UI runs require an unlocked screen (`hands probe session` ->
  `screen_locked:false`); results gathered while locked are invalid (the lock screen is frontmost, AX is blind).
- Reviewed PRs that pass tests may be merged by the lead without asking.
- Tinker: iterate beyond the $60 phase budget when results fall short (diagnose why, research, retry), but stay
  within the $150 hard cap.
- Model choices (planner, grounder, router incl. the trained one): ship a recommended default but keep every
  alternative selectable by flag/config; never delete an option until the user has reviewed it.
- Demo setup scripts (finance + advisor) are approved to run; HUD style = glass; Dock auto-hide is off for the demo.
- Nothing destructive, nothing outside this project; commit to GitHub often so any step can be reverted.

## Current serving configuration (`tools/serve_brain.sh`; every alternative selectable by env)
- Router + ARGS: Tinker-trained 4B iteration 2 (`models/route-4b-it2-mlx4`, HF `jonsnov/muselet-route-4b-main-mlx4`
  @ 54b2181), tau 0.65 (val-fitted). Alternatives: r2 @ 2e3e7bf, base `mlx-community/Qwen3.5-4B-4bit`.
  Quote router numbers on `evals/route_v1_clean.jsonl` (103 cases without near-duplicates in training data).
  Competitor benchmarks (HobbyLM sealed, DeskMind Bench) run ONLY with it2 or a later router whose overlap check is 0
  for that set (it2: HobbyLM r4 clean; DeskMind diag 1 affected task -> report with and without it). Never run r1/r2
  (main-final data: 12-15 near-duplicates per HobbyLM sealed round) on sealed sets.
- Planner: base 4B-4bit, greedy, `prompts/planner_fewshot.md` (rules 16-18 + examples), DSL history, line-start op
  constraint, done-alone. 35B-A3B via `--planner-model` or `ESCALATE=1`. Offline planner bench: `evals/planner_offline.py`
  (tune / holdout / holdout2 sets; never tune on holdouts).
- Grounder: eyes-4b, two-stage zoom, 1 MP (`click "<description>"` in the DSL), lazy-loaded; 2 MP / UI-Venus selectable.

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
overlay: mascot + ghost cursor flies to the element frame before acting; reply as text in the mascot bubble
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
- Keep System-1 speed on hard tasks: frequent multi-step workflows become catalog skills with `executor: brain`
  (router picks them in one forward pass; deterministic Python tools do the work and drive HandsKit), and the
  planner is the fallback for everything else.

## Process + protocol
`brain` (Python) runs a WebSocket server on `ws://127.0.0.1:8765`; the app connects as client.
The app owns all TCC permissions (Accessibility, Screen Recording, Microphone, Automation) and executes all OS actions.
One JSON object per frame; `t` = message type.

App -> brain:
- `{"t":"hello","screens":[{"id":1,"frame":[x,y,w,h],"scale":2.0}]}`
- `{"t":"utterance","id":"u1","text":"...","final":false,"ctx":{"app":"Notes","focused":"textarea \"Note body\"","selection":false,"online":true}}`
  (partials allow speculative prefill; `final:true` commits). `ctx` is captured by the app at push-to-talk
  key-down, before any Muselet UI appears: `app` = frontmost app's localized name; `focused` = the focused
  element as `<role> "<label>"` using the observation role names (or `none`); `selection` = focused element
  has non-empty `AXSelectedText`; `online` = current network reachability (no blocking probe). The brain owns
  `last_action` (`<skill> key=value ...` with the raw extracted arg strings, e.g. `start_timer duration="10 minutes"`).
- `{"t":"cancel"}`
- `{"t":"rpc_result","id":"r1","ok":true,"result":{...}}` or `{"t":"rpc_result","id":"r1","ok":false,"error":"..."}`
- `{"t":"confirm_reply","id":"c1","yes":true}`

Brain -> app:
- `{"t":"rpc","id":"r1","method":"<observe|act|skill|screenshot|verify|apps>","params":{...}}`
- `{"t":"ui","mascot":"idle|listening|thinking|acting|success|confused|sleeping","bubble":"optional text"}`
- `{"t":"say","text":"..."}` (shown in the mascot's speech bubble; no audio)
- `{"t":"confirm","id":"c1","summary":"Send the message to Mom?"}`
- `{"t":"confirm_cancel","id":"c1"}` (the confirm timed out or the task was cancelled; the app leaves confirm mode)
- `ui` may carry `"ms": 212` on the final message of a request: release-to-first-action for skills, total for
  planner/brain-tool tasks. The app shows it as a small latency chip next to the bubble for ~2 s.

RPC methods (HandsKit):
- `observe {scope:"focused_window"|"app"|"menubar", app?, max_nodes:150, diff:true}` ->
  `{epoch, app, window, focused_ref, elements:[{ref,role,label,value?,enabled,frame:[x,y,w,h]}], text, diff_text?, ax_ms}`
  Refs are valid for the returned `epoch`. Frames are global, top-left origin, points. Also `window_source`
  (focused|main|windows|app|none), `truncated`, and `web_ax_pending` (Chrome's web tree fills ~2 s after enabling).
- `act {op, ref?, text?, combo?, x?, y?, ..., epoch?, expect?}` -> `{ok, error?, act_ms, settle_ms, diff_text?, expect_ok?, observed?}`
  `expect` is sent as the DSL predicate string (e.g. `title~"Downloads"`). Refs are stable across epochs
  while the element persists; `rpc_result` always carries `result` when the handler produced one, even if `ok` is false.
  (fused act-and-observe; the app animates the ghost cursor to the target frame first, `cursor_lead_ms` default 120)
- `skill {name, args}` -> `{ok, result?, error?, ms}`. `type_text`/`type` fail with `error: "no_text_target"` and an
  `observed` hint when nothing focused accepts text (never "type into nothing"); Calculator accepts typed keystrokes
  (`target: "keystroke_app"`); shell scripts fail on non-zero exit (`exit_code`, `stdout`, `stderr`, `timed_out`).
  Launch skills verify the result: `open_app` -> `{app, frontmost, launched}`; `open_url`/`web_search` ->
  `{browser, frontmost, window_title, title_changed}`; `open_folder`/`open_file` -> `{app, frontmost, window_title,
  title_matches}`; failure `not_frontmost` (failures may carry `result`). `open_folder {view: list|icons|columns|gallery}`;
  `set_brightness {delta}` (alternative to `level`, returns `{level, previous, delta}`).
  `type`/`keys`/`click`/`type_text` fail with `screen_locked` while the lock screen is up.
- `act {op:"keys", combo: brightness_up|brightness_down|volume_up|volume_down|mute|play_pause|next_track|previous_track}`
  posts media keys and reads the level back (`media_key, level_before, level, changed`, `muted`).
- `timers {}` -> `{timers:[{id, label, total_s, left_s, minutes, fires_at}]}`; `timers_cancel {id?}` -> `{cancelled, timers}`
  (`unknown_timer: <id>`). CLI: `hands probe timers`, `hands probe session` (screen_locked, display asleep, frontmost).
- `screenshot {window:true, max_pixels:1000000, region?}` -> `{path, width, height, origin:[x,y], scale}` (own windows excluded)
- `verify {expect}` -> `{ok, observed}`
- `ocr {path? | region?:[x,y,w,h]}` -> `{text, lines:[{text, frame}], ms}` (Apple Vision, accurate, en-US; region = screen points)
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
# <note>                          (optional comment line, ignored by the executor, <= 20 words)
  predicates: title~"<text>" | focused #<ref> | value #<ref>="<text>" | app "<name>" | appears "<label>" | gone #<ref>
```

## Decision API (System 1)
`decide(state, questions) -> distributions`. Question kinds: `choice` (<= 58 options, ids from the alphabet
`A-Z 0-9 b d e f h i j k l m n o p q r s t u v x y z` in that order, i.e. every id that encodes as one token
after `choice#`; read as `choice#<id>` logits after a prefilled `choice#`), `bool`, `score`.
Renderer is tinker-cookbook `qwen3_5` (assistant turn starts with an empty `<think>\n\n</think>\n\n` before
the `choice#` prefill); `training/artifacts/route_render_samples.jsonl` is the token-level parity reference. Skills are shortlisted (embedding/BM25 top-K)
before the choice question; special options always present: MULTI_STEP, ASK, REFUSE, ANSWER.
Each question is prefilled on a snapshot of the cached state, so extra questions cost only their own tokens.

## Traces
Every interaction appends JSONL to `runs/traces/`: utterance, observations, model inputs, decisions + probabilities,
actions, results, per-stage latencies, final verification. Traces feed evals, failure replay and training data.

## Commands
- Python env: `uv run --project ml python ...` (deps pinned in `ml/pyproject.toml`)
- Speed lab: `uv run --project ml python bench/speed_lab.py --models <repo...> [--vlm-models <repo...>]`
- Devin Cloud: `python3 tools/devin_cloud.py create|msg|status|log ...` (new sessions default to `fusion` mode;
  reviewers use `--no-secrets`). Reviewer sessions are listed in `runs/reviewers.json`; findings live on
  `origin/review/<lane>` in `reviews/<lane>/{findings.jsonl,digest.md}`.
- Review heartbeat: `nohup tools/review_pulse.sh >> runs/review_pulse.log 2>&1 &` (snapshots local work to
  `wip/local` via `tools/push_wip.sh` and pulses reviewers when branches move; also logs Tinker spend to
  `runs/tinker_spend.jsonl` and sends the training session a pause/stop at $60 / $135). Add a reviewer lane:
  `tools/add_reviewer.sh <lane> cloud/review/<lane>.md`.
- Tinker spend: `python3 tools/tinker_spend.py` (billing data lags by up to a few hours).
- Local memory budget (the dev Mac is also the user's machine; it once ran out of memory): one main brain
  (:8765) plus at most ONE extra model process at a time; check `sysctl -n kern.memorystatus_level` >= 40 before
  loading a model; run model benchmarks sequentially and kill each process after its run; prefer cloud sessions for
  anything that doesn't need macOS. `nohup tools/mem_guard.sh &` kills agent benchmark processes below 25% free.

## Conventions
- Pin dependency versions; prefer releases at least 7 days old.
- No secrets in the repo; API keys only via environment variables (TINKER_API_KEY, HF_TOKEN, OPENAI_API_KEY, ANTHROPIC_API_KEY).
- Licenses: non-commercial datasets (e.g. GUIrilla CC-BY-NC) are allowed for the hackathon build only; track them in `data/LICENSES.md`.
- Never train on eval sets (ScreenSpot-Pro, OSWorld-G, UI-Vision, GUIrilla-Gold, HobbyLM frozen tests, DeskMind Bench, macOSWorld, MacAgentBench); dedupe training data against them.
