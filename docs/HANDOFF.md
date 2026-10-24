# Muselet: handoff for a new Devin org

Written Sat Oct 24 2026, ~14:00 PDT, by the lead agent. **Deadline: Cal Hacks submission Sun Oct 25 2026, 09:00 PDT.**
Repo: `github.com/ardahk/muselet` (branch `main`). Local Mac checkout: `/Users/arda/cal13.0`.
Read this file, then `AGENTS.md` (the project contract), then the workstream you are assigned in §7.
**Switching orgs?** The user follows `docs/NEW_ORG_SETUP.md`; the new lead starts from `docs/MASTER_PROMPT.md`
(one long prompt with the latest state, rules, first-hour checklist and priorities, including the memory
workstream W11).

---

## 1. Mission and hard constraints

- **Goal:** the fastest, most accurate, most capable fully on-device macOS computer-use agent. Beat **DeskMind**
  (github.com/deskmind-ai/deskmind) and **HobbyLM-1B Computer Use** on their own benchmarks, on this Mac, and on
  public benchmarks. Priority order: speed, then accuracy, then task complexity.
- **Runtime is 100% local** (Apple Silicon, MLX/ANE). The cloud is for development, data generation, training (Tinker)
  and review only.
- **Product:**
  - voice-first push-to-talk (Right Option), local STT (FluidAudio Parakeet on ANE);
  - no TTS: the mascot replies with ≤ 12 words in a speech bubble;
  - a cute desktop pet mascot (being redesigned as a kitten);
  - a ghost cursor shows where it acts.
- **Hardware target:** MacBook Pro M5 Pro, 64 GB, macOS 27. It is also the user's personal machine: memory and safety
  rules in `AGENTS.md` are mandatory.
- **Budgets:**
  - Tinker: **$150 hard cap**. $77.51 billed through 17:00Z Sat; the guard warns at $120 and stops at $140
    (`tools/tinker_spend.py`, `tools/review_pulse.sh`).
  - OpenAI / Anthropic data generation: up to **$200 per provider** (user-approved). Spend so far: about $114
    (decisions gen $52.89, data-route $61.17; data-planner step 2 just started, ≤ $90).
- **User standing decisions** (also in `AGENTS.md`):
  - tune every option's knobs fairly before calling anything "better" (tuned vs tuned), with a written
    hypothesis per knob change;
  - keep every model alternative selectable; ship a recommended default;
  - live UI tests run **only** through the runners, with mechanical preconditions. Never type into, edit or
    close documents a case did not create. The screen must be unlocked;
  - nothing destructive and nothing outside the project; commit often;
  - reviewed PRs that pass tests may be merged by the lead;
  - never train on any eval set (ScreenSpot-Pro, OSWorld-G, UI-Vision, GUIrilla-Gold, HobbyLM frozen tests, DeskMind
    Bench, macOSWorld, MacAgentBench, our route_v1/v2, live_t1, planner holdouts). Dedupe against all of them.

## 2. Status snapshot (Sat 14:00 PDT)

### Working on the Mac now
The app was rebuilt at main `68e76c6`+ and its brain runs the serving config on `:8765`.
- **System controls:** volume, brightness, dark mode, Wi‑Fi, Bluetooth, lock, battery, media keys. Compound
  commands ("volume to 20 and dark mode").
- **Apps / files / web:** open, hide and quit apps; open folders, files and URLs; web search; website-by-name
  ("wikipedia" -> wikipedia.org, Gmail is a website) in the **default browser (Zen)**; web pages are read through AX.
- **Multi-step:** a planner with expect checks; a grounded click (eyes-4b) when the AX tree is blind.
- **Demos:** Numbers finance review (duplicates, receipts via OCR, budget) and advisor meeting prep. Both are
  `executor: brain` tools.
- **Messaging (new):**
  - contacts-first flow;
  - Messages opens with the draft;
  - confirm "Send 'hi' to Caleb Kawano?", and only a yes sends;
  - the recipient is checked against the window title, header and To field only.
  The user's first live tries exposed parsing and resolution bugs; **comms-2** is fixing them (§7 W5).
- **Email drafting (new):** `draft_email` for Mail or Gmail; it reads the open email through AX, with an OCR
  fallback, and never sends without a confirm. Not yet live-tested.
- **Safety gates:**
  - confirm before send/delete/pay;
  - Enter-to-send confirmation in 13 chat apps plus web composers (including Zen);
  - grounded-click danger checks with OCR;
  - no typing into sign-in fields;
  - no typing with no text target;
  - permission-prompt gate: the agent asks the user instead of clicking "Allow" (brain-8, merged today);
  - relative paths are refused (HandsKit).

### Measured numbers (sources in `docs/REPORT.md`)

| Benchmark | Muselet | Competitor / baseline | Notes |
|---|---|---|---|
| Router, clean route_v1 (103) | **it2 .913** route acc, .857 end-to-end | base 4B .767 / .690; r2 .864 | Tinker LoRA on Qwen3.5-4B, MLX 4-bit |
| Planner offline (tune / holdout / holdout2) | **.88 / .643 / .667** | base config .68 / .50; 35B-A3B .84 / .71 | holdouts are the honest numbers |
| ScreenSpot-Pro (200-sample subset) | eyes-4b + zoom: **63.5%** (1 MP), 67.5% (2 MP) | UI-Venus-8B zoom 64.5% | not the full set |
| JevBench public | base 4B .719 | **DeskMind brain-4b .831**, brain-0.8b .723 | decisions LoRA in training (§7 W2) |
| Typed-decisions test | base 4B .569 | **DeskMind brain-4b .658**, 0.8b .540 | same |
| Live suite T1 / T2 (morning run, 27 of 43 ran) | **19/22** / 1/5; first action p50 193 ms, p95 812 ms | — | `runs/bench/live/20261024T161427Z`; a new run is in flight |
| HobbyLM sealed r4 (125, live) | **running now** | HobbyLM published **90/125 (72%)** | the same-Mac rerun of HobbyLM is optional (§7 W8) |
| DeskMind Bench diag (13×3, live) | not run | — | needs a zh-Hans locale (§7 W8) |

### In flight right now

| Who | What | Where |
|---|---|---|
| Mac sidekick | benchmark block: live suite + HobbyLM r4 Muselet | writes `/tmp/bench_block2_report.md`, `runs/bench/...` |
| Cloud A (training) | router **it3**: catalog v3 (43 options) + it3cand data + 35B soft labels, ≤ $140 total | Tinker; PR #2 `cloud/data-pipeline` |
| decisions builder | general decision LoRA, full run (LR 2e-4, 1 epoch, ~$23) | `cloud/decisions` |
| data-decisions | code-gold generators (diversity: counting, multi-hop, rule engines, dates, Bayes, traps) | `cloud/data-decisions` |
| data-planner | step 2: ~1,500 validated teacher demos + a retrieval bank | `jonsnov/muselet-planner-demos-v1` (pending) |
| comms-2 | messaging parser, iMessage-people-first, fuzzy answers (Python) | `cloud/comms-2` |
| mascot-animal | kitten mascot, same moods (Swift, uncompiled) | `cloud/mascot-animal` |
| clock-timers | timers in Clock via `shortcuts run` (Swift + Python) | `cloud/clock-timers` |
| planner-retrieval | BM25 1–2 shot examples from v2-tune (Python) | `cloud/planner-retrieval` |
| 10 reviewer lanes | continuous review of main + branches | `origin/review/<lane>` |

## 3. Architecture

```
push-to-talk -> STT (FluidAudio Parakeet TDT v2, ANE, streaming partials) -> brain (Python, ws://127.0.0.1:8765)
brain:
  deterministic pre-routes (calc, sites, draft_email.parse_request, compound split, slot answers, comms pending)
  System 1 router: one forward pass -> probabilities over catalog skills + MULTI_STEP/ASK/REFUSE/ANSWER (tau .65)
     confident skill -> ARGS extraction (same LoRA) -> code coercion (argfix, pathfind) -> HandsKit skill
     MULTI_STEP / low confidence -> System 2 planner (DSL action batches <= 5, expect per action)
  grounder eyes-4b (screenshot -> point, two-stage zoom) only when the AX tree is blind
  executor:brain tools (finance_review, advisor_prep, compose_text, draft_email, comms) drive HandsKit RPCs
HandsKit (Swift, inside Muselet.app): observe (AX), act, skills, screenshot, ocr, timers, contacts/messages RPCs
App: mascot + bubble + pill + ghost cursor; owns all TCC permissions; Settings behind the gear
```

Protocol, RPCs, DSL and observation format: `AGENTS.md`. Every interaction is traced to `runs/traces/*.jsonl`.

### Repo map (main entry points)
- `ml/src/brain/`: `orchestrator.py` (everything routes through it), `decision.py` (router/ARGS runtime),
  `planner.py`, `grounder.py`, `dsl.py`, `argfix.py`, `pathfind.py`, `sites.py`, `comms.py`, `sendgate.py`,
  `slots.py`, `tools/` (finance_review, advisor_prep, compose_text, draft_email), `server.py`, `cli.py`.
- `app/Sources/HandsKit/`: `RPC.swift` (dispatch), `Observe.swift`, `Act.swift`, `Skills.swift`, `WebAX.swift`,
  `Contacts.swift`, `MessagesCompose.swift`, `Timers.swift`, `OCR.swift`, `Screenshot.swift`.
- `app/Sources/MuseletApp/`: `App/` (AppDelegate, models, settings), `Mascot/`, `Panel/`, `Voice/`, `Overlay/`.
- `skills/catalog.json`: the single source of truth for skills (Swift + Python). Changing it affects route parity
  tests (`training/artifacts/route_render_samples.jsonl`).
- `prompts/`: planner system prompt + few-shot (lead-owned).
- `evals/`: route_v1 (+ clean), planner scenarios v1/v2 + offline bench, live_t1 (live suite), fixtures.
- `bench/`: harness (`harness/`), live runner (`live/run_live.py`), HobbyLM replay (`hobbylm/replay.py`), DeskMind
  runner (`deskmind/run_muselet.py`), System One shim + JevBench/typed-decisions scripts, ScreenSpot runner,
  `RUNBOOK.md`.
- `training/`: Cloud A's route data/renderer/trainer, `data_route/` (audit + it3cand), decisions trainer.
- `tools/`: `serve_brain.sh` (serving config), `devin_cloud.py` (cloud sessions), `tinker_spend.py`,
  `review_pulse.sh`, `mem_guard.sh`.
- `docs/REPORT.md` (training + evaluation report with sources), `docs/native_vs_muselet.md`, `pitch/claims.md`.

## 4. Models and artifacts

| Role | Default | Alternatives (selectable) | Where |
|---|---|---|---|
| Router + ARGS | it2: Qwen3.5-4B LoRA, MLX 4-bit, tau .65 | r2 `2e3e7bf`, base `mlx-community/Qwen3.5-4B-4bit` | `models/route-4b-it2-mlx4`, HF `jonsnov/muselet-route-4b-main-mlx4` @ `54b21817` |
| Planner | base Qwen3.5-4B-4bit, greedy, few-shot + DSL history + line-start constraint | Qwen3.6-35B-A3B-4bit (Settings toggle, ≥ 48 GB) | `prompts/planner_*.md` |
| Grounder | deskmind/eyes-4b, two-stage zoom, 1 MP, lazy | 2 MP, UI-Venus-1.5-8B | `ml/src/brain/grounder.py` |
| Decision model | base 4B (no LoRA yet) | decisions LoRA (training) | `cloud/decisions` |
| STT | FluidAudio Parakeet TDT v2 | — | app |

Datasets (private HF, `jonsnov`):
- `muselet-route-datums-main` @ `2bd81d8`: r1/r2 data. **Contaminated** (HobbyLM near-dups); never use it for sealed
  benchmarks.
- `muselet-route-datums-it2b` @ `8df540b`: clean it2 pool.
- `muselet-route-datums-it3cand` @ `84595279`: audited + targeted. 41,756 route + 30,152 ARGS rows; catalog v3;
  0 overlaps.
- `muselet-decisions-v1` @ `9683da5`: about 14.4k decisions, about 2,220 code-gold states.
- Tinker checkpoints: it2 `tinker://73495408-9d6d-56b5-9e1a-894744c13add:train:0/sampler_weights/it2-final`
  (it2-200/-400/-final kept).

Recipe (router): LoRA r32, LR 4e-4 (two pilots), 1 epoch, batch 128, 60/40 route/ARGS. Soft targets
0.6·onehot + 0.4·teacher (Qwen3.6-35B on Tinker); Sonnet adjudicates disagreements; 30% ASR-noise augmentation.
Export: MLX 4-bit with an **untied lm_head** (the first export tied it and broke ARGS).

## 5. How to run things (Mac)

```sh
cd /Users/arda/cal13.0
uv run --project ml python -m pytest ml/tests -q          # ~1350 tests
uv run --project ml python -m pytest bench/tests -q       # ~162 tests (run separately from ml/tests: basename clash)
(cd app && swift build && swift test --scratch-path .build-hands)   # ~206 Swift tests
bash app/scripts/build_app.sh && open app/build/Muselet.app          # signed app bundle
nohup tools/serve_brain.sh > /tmp/brain8765.log 2>&1 &               # main brain :8765 (serving config)
PORT=8766 nohup tools/serve_brain.sh > /tmp/brain8766.log 2>&1 &     # benchmark brain
sysctl -n kern.memorystatus_level   # must be >= 40 before loading another model; max one extra model process
```
Benchmarks: `bench/RUNBOOK.md`, which gives exact commands for the live suite, HobbyLM r4, DeskMind diag, JevBench,
typed-decisions and the calendar safety setup. Before any live run, `app/.build/release/hands probe session` must
show `screen_locked:false` and `main_display_asleep:false`.

## 6. Cloud operations in a new org

1. In the new org:
   - connect GitHub with access to `ardahk/muselet`;
   - create a **service user** with session-create and message permissions (add `ViewOrgConsumption` if you want
     usage numbers);
   - add org secrets `TINKER_API_KEY`, `HF_TOKEN` (write access to `jonsnov/*`), `OPENAI_API_KEY` and
     `ANTHROPIC_API_KEY`.
2. On the Mac, put the new `DEVIN_API_KEY` (service-user token, `cog_…`) and `DEVIN_ORG_ID` (`org-…`) into
   `/Users/arda/cal13.0/.env`. `tools/devin_cloud.py` reads them and passes the four model/data secrets to every
   session.
   ```sh
   python3 tools/devin_cloud.py create --title "muselet build: <lane>" --prompt-file cloud/handoff/<lane>.md
   python3 tools/devin_cloud.py msg <session_id> --text "..."      # steer
   python3 tools/devin_cloud.py status <session_id>; python3 tools/devin_cloud.py log <session_id> -n 5
   ```
   Reviewer lanes: `tools/add_reviewer.sh <lane> cloud/review/<lane>.md` (use `--no-secrets`). The heartbeat
   `tools/review_pulse.sh` pulses reviewers when branches move.
3. Conventions:
   - one branch `cloud/<lane>` and one PR per builder; the lead reviews and merges;
   - builders never merge, never edit `prompts/` or `evals/` (lead-owned), never start Tinker runs unless their
     brief says so;
   - Swift written in the cloud is uncompiled; a Mac agent compiles and fixes it.
4. The old org's sessions (`runs/builders.json`, `runs/reviewers.json`) stop when its credits run out. Their
   branches and PRs stay on GitHub, so continue from the branch.

## 7. Workstreams: paste-ready briefs live in `cloud/handoff/`

Each brief states the goal, current state, exact next steps, acceptance criteria and pitfalls:

| ID | Brief | Priority | Needs Mac? |
|---|---|---|---|
| W1 | `cloud/handoff/W1_router_it3.md`: finish/evaluate/export it3, deploy behind a flag | P0 | eval + parity on Mac |
| W2 | `cloud/handoff/W2_decisions.md`: decisions LoRA eval vs DeskMind, calibration, export | P0 | JevBench/TD on Mac |
| W3 | `cloud/handoff/W3_data.md`: data-quality lanes (route residue, code-gold, planner demos) | P1 | no |
| W4 | `cloud/handoff/W4_planner.md`: retrieval eval, v2 bench numbers, optional planner LoRA | P1 | eval on Mac |
| W5 | `cloud/handoff/W5_comms.md`: messaging/email polish (Python) + the Swift contract | P0 | Swift on Mac |
| W6 | `cloud/handoff/W6_app_ui.md`: kitten mascot, panel polish, screenshots | P0 (demo) | compile on Mac |
| W7 | `cloud/handoff/W7_clock_timers.md`: Clock timers via Shortcuts | P1 | verify on Mac |
| W8 | `cloud/handoff/W8_benchmarks.md`: live suite, HobbyLM r4, DeskMind zh-Hans, report numbers | P0 | Mac only |
| W9 | `cloud/handoff/W9_safety_backlog.md`: open review findings to fix | P1 | partly |
| W10 | `cloud/handoff/W10_report_pitch_demo.md`: REPORT.md, claims.md, demo script, video | P0 (Sun AM) | rehearsal on Mac |
| W11 | `cloud/handoff/W11_memory.md`: memory (follow-up resolution, working + long-term + episodic/procedural memory) | P0 (user's new priority) | eval + live cases on Mac |

## 8. Safety rules and incident history (read before touching the Mac)

- **Incident (Fri night):** a manual E2E typed into the user's open TextEdit document (`projectZ/.env`), and autosave
  wrote it. Since then:
  - live cases run only via runners, with a mechanical precondition + document inventory;
  - teardown closes only what a case created;
  - `type_text` fails with `no_text_target` when nothing editable is focused.
- **Incident (Sat AM):** the planner pressed **Allow** on a macOS permission prompt during a live case. brain-8 now
  gates every action while a TCC/auth dialog is frontmost and asks the user instead.
- **Incident (Sat AM):** `new_folder parent="my desktop"` created the folder inside the repo (the hands process
  CWD). HandsKit now refuses relative paths and the brain normalizes folder names.
- **Messaging:**
  - never send to an unresolved raw name;
  - confirm with the resolved name;
  - the recipient check reads only the title, toolbar header and To field. Never the sidebar or transcript: a
    name there would verify the wrong conversation.
- **Locked-screen results are invalid** (the lock screen is frontmost). Use `caffeinate -dimsu` during runs.
- **Memory:** the Mac once ran out of memory. Run one main brain + at most one extra model process, check
  `kern.memorystatus_level` ≥ 40, and keep `tools/mem_guard.sh` running.
- Never touch `/Users/arda/projectZ/.env` (the user rotates those keys) or anything outside the repo, except
  benchmark sandbox paths the runners create.

## 9. Known bugs / backlog, from today's live traces

1. **Messaging parse** (comms-2 in progress):
   - "send a hello message to Arda" went to Mail;
   - STT self-corrections in names;
   - "Ardaoke" didn't match Arda Hoke;
   - re-saying a full command while a question was pending;
   - "send a text to Monica" lost its slot, and the answer "Say hello." was typed into the IDE.
2. **Messages compose race:** the front window isn't ready right after `imessage:` opens it, so compose returns
   `no_text_target`. Add a ≤ 2 s poll for the window and compose field (Swift; in W5's Swift contract).
3. **Recipient check:** the Swift `contactName(for:)` phone lookup returned nil for Caleb, so compose said
   `recipient_unverified` even though the title was "Caleb Kawano". Fix: pass `name` from the brain (W5 contract).
4. **Router it2** labels some "message" requests compose_email: label noise in it2b, fixed in the it3cand data
   (W1).
5. **Notes template** ("open Notes and write a template about my day"): compose_text exists (brain-7) but has
   not been re-tested live.
6. **Files/Finder multi-step** was weak in the morning run (2/7); fixed by brain-8 (paths) plus grader fixes,
   pending re-measure.
7. **Web answers** ("look up when the Golden Gate opened") are now implemented (brain-8) but not yet measured.
8. Review backlog: `cloud/handoff/W9_safety_backlog.md`.

## 10. Decision log (key calls, with evidence)

- it2 router over r2/base: clean route_v1 .913 vs .864 / .767 (tuned tau per model).
- The 4B planner stays the default. The 35B is optional (better holdout .71, but 2–2.7× slower, +19 GB). The 9B
  was worse and slower.
- Grounder: 1 MP + two-stage zoom (63.5%), with 2 MP selectable (+4 pts, +0.85 s).
- Decisions LR 2e-4 over 4e-4. Route val was the hard gate; the dev gaps were tiny. JevBench was noted, not used
  to select.
- it3: catalog v3 (draft_email / compose_text routable), it3cand data, 35B soft labels for unlabelled items.
- Competitor benchmarks only run with routers whose overlap with that set is 0 (it2 and later).
- The HobbyLM same-Mac rerun is optional. If Muselet's strict score beats HobbyLM's published, more lenient
  90/125, the claim is conservative. Rerun only if it doesn't.
- DeskMind Bench: tasks are in Chinese and their protocol uses zh-Hans. A log-out would kill the lead's session,
  so the plan is the global AppleLanguages + relaunching the apps under test, disclosed (W8).
