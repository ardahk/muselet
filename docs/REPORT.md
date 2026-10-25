# Muselet: models, evaluation and results (2026-10-24, updated 2026-10-25 for the demo build)

What was trained, how it was measured, what the numbers are, and what is still missing. Every number has a
source. Sources outside `main`: **PR #2** = branch `cloud/data-pipeline` (route training, `training/reports/`);
**cloud/decisions** = the System One decisions branch. `runs/` is gitignored, so `runs/...` paths exist only on the
Mac (M5 Pro, 64 GB, macOS 27). "Lead" = numbers reported by the lead from the Mac runs on 2026-10-24.

## 0. What ships (Sun 2026-10-25; `tools/serve_brain.sh`, `AGENTS.md` "Current serving configuration")
- **System 1** = router it3 (catalog v3, tau .50), one forward pass, acts directly only for OS-level skills
  (`kind: system` in `skills/catalog.json`: 26 skills such as volume, brightness, dark mode, Wi-Fi, apps, files, URLs).
  `kind: analysis` skills (`finance_review`, `advisor_prep`) are AI-planned through generic live-state
  tools like other app intents; the deterministic `executor: brain` finance/advisor workflow engines were
  deleted (a2004d9) and `AGENTIC_APPS=0` does not restore them.
- **Agentic apps** (`AGENTIC_APPS=1`, default): the 12 `kind: app` skills (Clock timers, Reminders, Calendar, Notes,
  Messages, Mail/Gmail drafts and replies, Music, Premiere) are operated by the planner over Accessibility
  (observe -> act -> verify) via `Orchestrator._agentic_route`, with a rule-based "Finish when" criterion
  (`ml/src/brain/finish.py`, no model call). Programmatic evidence ends the task as soon as the goal is visible
  (Pause button for media, cart count +1 over the baseline, Clock live row, draft text in the reply box).
- **Planners** (script defaults — the deployed Mac overrides them; see below): fine-tuned LoRA 4B for normal
  multi-step tasks (holdout mean .850, ~0.3 s per step); Qwen3.6-35B-A3B
  (MoE, ~3B active, think 512, retrieval k=1, app hints) as the blind planner (`BLIND_PLANNER=escalate`, default when
  the weights are cached) for page/browser tasks, open-ended asks, recoverable-failure fallbacks and any turn whose
  AX observation is blind. `BLIND_PLANNER=base|planner` keep the base 4B or the LoRA selectable. The offline planner
  numbers in §4 are unchanged.
- **Browser**: same tab within a task; the site's own search box (hand-built same-site search URLs and address-bar
  queries are rejected); default browser read from LaunchServices; expects on a loading page re-poll for up to 5 s.
- **Safety**: confirm before send/delete/buy/post; grounded (pixel) clicks blocked in apps holding user data (see
  "Incidents and fixes"); planner AppleScript/JXA that does UI scripting (`click`, `perform action`, `keystroke`, ...)
  needs confirmation; shell scripts always do.
- **Not measured on this build yet**: no live-suite, HobbyLM or DeskMind Bench run exists for the agentic-apps /
  35B-blind configuration. Every number below was measured on the configuration named in its row.
- **Deployed override vs script defaults**: the Mac's live brain runs `tools/serve_brain.sh` with env overrides —
  `PLANNER=base` in native-tools mode (`--planner-mode tools`), `BLIND_PLANNER=planner`, `PLANNER_AUX=planner`,
  `THINK=1024` qwen sampler, `FEWSHOT=none`, `RETRIEVAL_K=0`, escalation off (`MUSELET_NO_ESCALATE=1`,
  `ESCALATE=0`), `APP_HINTS`/`OPEN_ENDED`/`AGENTIC_APPS`/`VERIFY_DONE`/`FALLBACK_PLANNER`/`PLANNER_CONTEXT` on
  (exact env in `AGENTS.md` "Deployed runtime override"). The LoRA/35B timings in this report are measurements of
  those named configs, not of this deployment.

## 0a. Reliability coverage (2026-10-25)

Regression evidence for the app-discovery + Premiere focus/observation fixes — hermetic test suites, not a
benchmark and not a claim of live editing success:
- `uv run --project ml python -m pytest ml/tests/test_obsdiff.py ml/tests/test_premiere_focus_progress.py
  ml/tests/test_app_hints.py -q` → 63 passed (plus `test_first_use_fixes.py
  -k identical_noop_presses_trip_loop_guard`).
- `xcodebuildmcp swift-package test --package-path app --filter 'AppResolverTests|TruthfulLaunchTests'` →
  31 passed.
- `uv run --project ml python -m pytest ml/tests/test_apps_notes_regressions.py ml/tests/test_native_site_rewrite.py -q`
  → 173 passed (`runs/appresolver_after_pytest.log`: spoken-name resolution incl. versioned/alias cases).
- `uv run --project ml python -m pytest ml/tests/test_grounder_wire.py
  -k 'observation_blind or planner_user_message_gets_blind_hint' -q` → 19 passed
  (`runs/premiere_identification_checks.log`: real "Adobe Premiere" localized name recognized as canvas/blind).
Covers: shared recursive installed-app enumeration (nested vendor bundles such as `Adobe Premiere Pro 2026`),
unique year-suffix name resolution, the real `Adobe Premiere` canvas-app name, the consecutive `shift+3`
focus guard with model feedback, fresh AX observation for UI-only turns, and numeric/HotText value
preservation in diff-chained observations. No live Premiere editing pass is claimed; live E2E still needs a
guarded runner measurement.

The final full-suite attempt (`uv run --project ml python -m pytest ml/tests -q`) did not complete.
Its local log (`runs/github_final_python.log`) stopped at 65% with failure markers and no final summary.
Those wider failures remain untriaged; there is no baseline establishing that they predate these changes.
The targeted passes above must not be presented as a green full-suite result.

## 1. Models

| Role | Serving default | Alternatives (selectable) | Source |
|---|---|---|---|
| Router + ARGS (System 1) | it3: Qwen3.5-4B + Tinker LoRA, MLX 4-bit, `jonsnov/muselet-route-4b-it3-mlx4` @ e057412, catalog v3 (43 options), tau .50 (val-fitted); acts directly only for `kind: system` skills, app skills go to the planner (`AGENTIC_APPS=1`) | it2 `jonsnov/muselet-route-4b-main-mlx4` @ 54b2181 (tau .35 tuned; .65 earlier), r2 @ 2e3e7bf (tau .45), r1 (tau .55), base `mlx-community/Qwen3.5-4B-4bit` (tau .20) | lead (user's call, §4); `tools/serve_brain.sh` |
| Planner (System 2) | planner LoRA 4B (`jonsnov/muselet-planner-4b-lora-mlx4` @ 35a2ea3), greedy, no few-shot, retrieval k=1, THINK=0, DSL history, line-start op constraint, done-alone | `PLANNER=base`: base Qwen3.5-4B-4bit + few-shot + think 512 | `tools/serve_brain.sh` header, `AGENTS.md` |
| Blind planner (System 2) | Qwen3.6-35B-A3B-4bit (MoE, ~3B active), think 512 (qwen sampler), retrieval k=1, app hints, batch cap 2; browser / open-ended / fallback / blind-observation turns (`BLIND_PLANNER=escalate`, default when cached) | `BLIND_PLANNER=base` (base 4B, few-shot + think 512), `planner` (the LoRA) | `ml/src/brain/cli.py` (`planner_blind`), `orchestrator.py` (`blind_task`) |
| Grounder | deskmind/eyes-4b, two-stage zoom, 1 MP, lazy-loaded (`click "<description>"`) | 2 MP, UI-Venus | `AGENTS.md:46`, `ml/src/brain/grounder.py` |
| Decisions (System One) | generalist decisions LoRA (§2.4); not used by the router path | base Qwen3.5-4B zero-shot | `training/decisions/results.md` (#39), lead |
| STT | FluidAudio Parakeet TDT v2 on the ANE | Apple SpeechTranscriber | `pitch/claims.md` §2 |

## 2. How each model was trained

### 2.1 Shared router recipe (SPEC Phase 1, PR #2 `training/SPEC.md` §1.3-1.6)
- **Task.** One forward pass over the request; read the `choice#<id>` logits over the 37 catalog skills plus
  MULTI_STEP / ASK / REFUSE / ANSWER. The same LoRA also learns ARGS extraction (plain chat SFT).
- **Data.** Synthetic utterances per skill with app/focus/selection/online/last-action context, generated by API
  teachers (`claude-haiku-5-5` generation, `gpt-5.4-nano` fallback; SPEC lines 19-21), ASR-noise augmentation on 30%
  of route items (route only, not ARGS), grounded-ARGS filtering (1,059 ungrounded ARGS dropped),
  `training/reports/phase1_fixes.md`.
- **Soft labels.** `target = normalize(0.6 * onehot(intended) + 0.4 * teacher_probs)` (SPEC §1.4). Teacher =
  `Qwen/Qwen3.6-35B-A3B` on Tinker (397B only on small adjudication subsets), exact softmax over all choice tokens in
  chunks of 18 ids (`training/src/muselet_train/teacher.py`). Where the teacher's argmax differs from the intended
  label with p >= 0.7, `claude-sonnet-5-5` adjudicates keep / relabel / drop (`adjudicate.py`).
- **Decontamination.** Training rows dropped against route_v1, live_t1 and the 570 HobbyLM / DeskMind external
  utterances (`phase1_fixes.md`); later a hard gate (normalized exact, word 13-gram, token edit <= 1 when either side
  has <= 5 tokens) that aborts training before spend (`evalcheck.py`, commit 19737e1). See §3.2.
- **LoRA / optimizer** (both full runs, from each report's config block): base `Qwen/Qwen3.5-4B`, rank 32, Adam,
  LR 4e-4, 1 epoch, batch 128, 60/40 route/ARGS mix, 496 steps. LR was picked by two pilots (`phase1_pilot-lr2e-4.md`,
  `phase1_pilot-lr4e-4.md`, est. $1.93 each).

### 2.2 `main` -> r1 / r2 (`training/reports/phase1_main.md`)
- 36,580 route + 27,023 ARGS training items; 37.6 M train tokens; est. $29.45.
- Full val split (1,130 route / 792 ARGS): top-1 .918, macro-F1 .885, ECE .016, ARGS EM .869. Weak labels: ASK 0/3,
  media_control .316, dark_mode .684.
- r1 = first merged export (broken head for ARGS, `serve_brain.sh:7`). r2 = `main-final` re-exported with an untied
  `lm_head` (commit f39efe4), HF revision 2e3e7bf.

### 2.3 it2 (`phase1_it2_plan.md`, `phase1_it2.md`)
- Same settings as `main`, so only the data changes: reader fixes (G3 dropped, constrained contexts), ASK by rule
  (`ask_rule.py`), strict `finance_review` relabels (`finance_check.py`), and 111 top-up requests for confusable
  pairs (dark_mode vs brightness, find_file vs open_file, reminder vs event, media vs Premiere playback, ASK hard
  negatives). Hypotheses were written before launch and judged on route_val only.
- 38,162 route + 25,441 ARGS items; 38.9 M train tokens; est. $30.44.
- Full val split (1,216 route / 878 ARGS): top-1 .938, macro-F1 .931, ECE .021, ARGS EM (runtime rendering) .869;
  ASK 11/12.
- Export: untied-head merge, MLX 4-bit, `jonsnov/muselet-route-4b-main-mlx4` @ 54b2181; parity file
  `artifacts/parity_300_it2.jsonl`.
- it2b (9 more training rows filtered, `evalcheck/it2b_filter.json`) exists as a 0-overlap option; it is not served.

### 2.4 Generalist decisions LoRA (in progress, branch `cloud/decisions`)
- **Goal.** Beat DeskMind brain-4b on JevBench and typed-decisions without losing System-1 speed; one adapter
  multi-tasked with the route data (>= 30% route replay), same soft-label loss as the router
  (`training/decisions/SPEC.md` "Split + datums"). The primary model never trains on typed-decisions, so its score
  stays zero-shot (`cloud/builder_decisions.md`).
- **Data plan.** About 40% code-gold families (temporal, numeric, counting, multi-hop, probability) whose gold is
  computed by code; teacher-gold families (judge, tradeoff, ambiguous, trap, agent_step, ordinal rubric, ...)
  authored by `gpt-5.4-mini` / `claude-sonnet-5-5` (SPEC "Mix").
- **Teachers / soft labels** (SPEC amendments 2-3): code-gold = reasoning teacher sampled K=4, target = empirical
  distribution (floor 1e-3), kept only if the majority equals the code gold; authored = 0.5 x `gpt-5.4-nano` (K=4) +
  0.5 x `gpt-4.1-mini` logprobs, kept only if they agree.
- **Generation done** (`training/decisions/reports/full_gen.md`, commit e125c13): 16,539 decisions generated;
  **6,754 decisions / 1,748 states retained** after labels and decontamination (choice 2,668 / noul 2,478 / score
  1,608). Decontam vs JevBench public, typed-decisions test and our evals removed 1,925 of 3,673 states (13-gram);
  remaining overlaps 0. Only 301 code-gold states survived (none from counting, multi-hop or long-policy). Train
  1,661 / dev 87 states. Uploaded privately to `jonsnov/muselet-decisions-v1`.
- **Not yet in the repo:** LoRA settings, a training run, or any eval of the trained adapter.

### 2.5 Cost
- **Tinker total: TBD(console)** of the $150 hard cap. Known: $136.22 on the console at Sat 2026-10-24 14:30 PDT,
  plus the planner LoRA (~$0.84 est.) and small sampling since (lead); `tools/tinker_spend.py` lags by hours. Hard stop $148. Earlier snapshots ($34.60, $64.89, $77.51)
  are superseded. The docs lane spent $0. Per-run estimates: pilots
  $1.93 each, `main` $29.45, it2 $30.44 (report config blocks; estimates, not bills).
- **API generation for decisions** (OpenAI + Anthropic, separate from Tinker): $52.89 cumulative of the $57 cap in
  `full_gen.md`. The user has since raised the cap: up to $120 for decisions, $200 per provider overall (lead,
  2026-10-24). Projected Tinker cost of a 20k-decision run: $12.28 (`full_gen.md`).

## 3. How each model is evaluated

### 3.1 route_v1 and the clean subset
- `evals/route_v1.jsonl`: 140 hand-written requests with route + ARGS gold. Runner:
  `uv run --project ml python -m brain.cli eval-route --model <router> --cases <file>`; tau fitted on val by
  `evals/router_check.py`.
- **Quote only the clean subset** `evals/route_v1_clean.jsonl` (103 cases; identical to `route_v1_clean_both.jsonl`):
  37 of 140 cases have a short near-duplicate in main-final's training data; it2's 7 affected cases are among them
  (`training/reports/evalcheck/clean_subsets.json`).

### 3.2 Overlap checks (`training/src/muselet_train/evalcheck.py`, reports in `training/reports/evalcheck/`)
| Eval set | main-final (r1/r2) | it2 | Rule |
|---|---|---|---|
| route_v1 | 37 | 7 | quote clean 103 only |
| live_t1 | 10 | 0 | it2 only |
| HobbyLM sealed-r4 (125) | 15 | 0 | it2 only |
| HobbyLM sealed-r1 / r2 / r3 | 12 / 13 / 10 | 0 / 1 (A04) / 1 (D09) | not quoted |
| DeskMind Bench diag / dyn | 1 / 16 (not re-traced) | 0 / 0 real | it2 only |

The DeskMind hits were a normalizer artifact: the old `norm()` kept only `[a-z0-9']`, so Chinese task text shrank to
"archive" or "" and sat one edit from "unmute"; it2's training rows contain 0 CJK characters (0 of 65,697,
`external_affected_it2.json`). The CJK-aware re-run (`it2_report_v3.json`, commit 512cce0) reports DeskMind 0 and
HobbyLM sealed-r2 1, sealed-r3 1, r4 0. Never quote r1/r2 on any sealed set (`AGENTS.md:40-42`).

### 3.3 Offline planner bench (`evals/planner_offline.py`)
Retrieval (`cloud/handoff/notes/planner-retrieval.md`): BM25 over the v2-tune bank, k examples appended to the
dynamic state. Decision rule fixed before the sweep: ship the smallest k whose mean gain over k=0 on the three
held-out sets is >= .03 and whose v2-holdout TTFT p50 rises <= 150 ms (pre-registered).
One planner turn per scenario, no UI. Pass = every line parses as DSL, the first action matches `accept_first`, no
line matches `reject_any`, and nothing in `confirm_before` appears before a `confirm`. Sets: **tune** (25, used for
the knob sweep), **holdout** (14, written after the sweep), **holdout2** (12, written after holdout-1 was used to
derive prompt rules 16-18; commit ec9684e). Never tune on the holdouts (`AGENTS.md:44-45`).

### 3.4 ScreenSpot-Pro subset (`bench/grounding/run_screenspot.py`)
200-sample stratified, paired subset of ScreenSpot-Pro, mlx-vlm 4-bit, screenshots capped at ~1 MP, optional
two-stage zoom (`bench/grounding/README.md`). Eval set only, never trained on.

### 3.5 JevBench / typed-decisions (`bench/systemone/`, `bench/run_jevbench.sh`, `bench/run_typed_decisions.sh`)
Our `POST /v1/systemone` shim answers DeskMind-style typed questions (`choice`, `noul`, `score`). JevBench public
(231 items, official CLI, pinned 609a664) and the typed-decisions test split (400 cases / 2,000 decisions; pinned
80cb93a; scorer copied verbatim, `bench/typed_decisions.py`). DeskMind brain-0.8b / brain-4b (G18b, 8-bit) run on
the same Mac through the same runners (`bench/RUNBOOK.md`).

### 3.6 Live suite (`bench/live/run_live.py`, `evals/live_t1.jsonl`)
43 tasks (33 T1 single-skill / routing, 10 T2 multi-step), run through the real stack and graded by final state,
never by what the agent said (`evals/live_t1.md`). Metrics: strict pass per tier, pass^3, false-done, confirms
asked, latency. Safety guards (`bench/live/README.md`, `bench/RUNBOOK.md`):
- `hands probe session` before each case; locked or asleep screen -> `screen_locked` skip (results gathered while
  locked are invalid).
- Document-app inventory before setup; an open user window or document -> `user_documents_open` skip; teardown closes
  only items the case created, never broad closes. Terminal apps are excluded, a stated residual risk.
- Sandbox `~/MuseletSandbox`, never replaced if it exists and removed afterwards; `restore` writes back volume,
  appearance and clipboard.
- `forbid` predicates for side effects; `confirm_reply` per case (null = fail if asked); RPC safety blocking on by
  default (`--no-safety-guard` labels every result unsafe).
- Manual, pending, online and `requires_user_ok` cases are skipped unless explicitly opted in.

### 3.7 HobbyLM / DeskMind harnesses
- **HobbyLM** (`bench/hobbylm/replay.py`): frozen r1-r4 inputs vendored unchanged at pinned 4ea1389
  (`upstream/PROVENANCE.md`); `--system muselet|hobbylm --round r4`; same session probe and document guard; event
  tasks run only against an isolated local "Muselet Bench" calendar that is the default (`calendar_safety.py`),
  otherwise they are skipped.
- **DeskMind Bench** (`bench/deskmind/run_muselet.py`): pinned suite `diag-v27` (hash 5eec62a0c662, 13 tasks x 3),
  DeskMind Hands 89be730, locale zh-Hans; the runner refuses a different suite hash or Hands commit; DeskMind is
  re-run on the same Mac at the same pin, because published numbers from other harness versions are not comparable.

## 4. Results

| Benchmark | Muselet | Comparison | Source |
|---|---|---|---|
| Router, tuned vs tuned (each at its val-fitted tau): val acc / macro-F1 / ARGS exact / route_v1_clean (103) / route_v2 (v2-catalog subset) / ECE / route p50 | **it3 @ .50 (serving): .926 / .924 / .855 / .922 / .945 (.940) / .018 / 60.4 ms** | it2 @ .35: .929 / .925 / .856 / .942 / .838 (.926) / .104 / 55.9 ms | lead, Mac MLX; `runs/router/{it2,it3}_{val,route_v1_clean,route_v2}.json` via `evals/router_check.py` |
| Router it3 ship decision | it3 serves by the user's call; the pre-registered rule (route_v1_clean >= it2 - 1 pt) was **not met** (-2.0 pt). it3 wins route_v2 (+10.7 pt) and calibration (ECE .018 vs .104) | - | lead |
| Router it3 export parity vs Tinker sampler | top-1 agreement .983 on `parity_300` | - | lead; HF `jonsnov/muselet-route-4b-it3-mlx4` @ e057412 (`parity_300.jsonl`) |
| Router, older setting: route_v1 clean acc / macro-F1 / ARGS / route+ARGS | it2 @ tau .65: .913 / .892 / .947 / .857 | r2 .864 / .866 / 1.000 / .857; base .767 / .825 / .784 / .690 | lead; r2 + base: `runs/router/r2_self_clean.json`, `base_clean.json` |
| Router val top-1 (it2's own val split, earlier run) | it2 .938 | main .912 | lead; `tools/serve_brain.sh:5` |
| Router it3 provenance | trained on `jonsnov/muselet-route-datums-it3@4ded9ab`, catalog v3 (43 options); overlap with eval sets 0 (lane brief) | - | HF `jonsnov/muselet-route-4b-it3-mlx4` @ e057412 |
| Router latency p50 (r2) | route 52 ms, ARGS 97 ms | - | `pitch/claims.md` §1a |
| Planner bench, shipped 4B + retrieval k=1: tune / holdout / holdout2 / v2-holdout | **.880 / .714 / .750 / .462** (22/25, 10/14, 9/12, 60/130) | same prompt k=0: .840 / .643 / .667 / .400 (21/25, 9/14, 8/12, 52/130); k=2 .714 / .750 / .462 on held-out, rejected (v2-holdout TTFT +156 ms > +150 ms gate); base config .68 / .50; 35B-A3B k=0 v1 sets (older run) .84 / .71, k=1 TBD(35B k=1 planner run, Mac) | `cloud/handoff/notes/retrieval_eval.md`; base/35B: lead, `runs/planner_offline/` |
| Planner TTFT p50 on v2-holdout (k=0 / k=1) | 113.4 / 184.6 ms (prompt 3,284 / 3,477 tokens) | - | `cloud/handoff/notes/retrieval_eval.md` |
| Planner thinking, held-out v1-ho / v1-ho2 / v2-ho (mean), all with retrieval k=1 | **4B think 512, Qwen sampler (`PLANNER=base` config; was serving until the LoRA): .786 / .917 / .608 (.770), step p50 2.6 s, p95 7.8 s** | no-think baseline .714 / .750 / .462 (.642), ~0.15 s; 4B think 512 greedy .763 mean @ 1.7 s; 35B think 512 .807 mean @ 6.0 s p50 (fails the 3 s gate); 35B no-think .601 mean | `cloud/handoff/notes/planner_think_eval.md` @ c9a5cce |
| Planner LoRA (2 epochs, Tinker), retrieval k=1, THINK=0 (serving): v1-ho / v1-ho2 / v2-ho (mean) | **.857 / 1.000 / .692 (.850), step p50 ~0.3 s** | base 4B think 512 .786 / .917 / .608 (.770) @ 2.6 s; LoRA k=0 .857 / 1.000 / .623 | lead; `tools/serve_brain.sh` header; HF `jonsnov/muselet-planner-4b-lora-mlx4` @ 35a2ea3 |
| Planner speed (4B, earlier config) | 139 ms per turn p50, TTFT 72 ms, 83 tok/s | 35B ~310 ms, 128 ms, 82 tok/s | `pitch/claims.md` §1a |
| ScreenSpot-Pro subset (200), eyes-4b two-stage zoom | 63.5% at 1 MP, 67.5% at 2 MP | no zoom 36.0% / 50.5% | lead (run path not given) |
| JevBench public | base Qwen3.5-4B .719 | DeskMind brain-4b .831, brain-0.8b .723 | `pitch/claims.md` §1a |
| Typed-decisions test | base .569 | brain-4b .658, brain-0.8b .540 | `pitch/claims.md` §1a |
| Decisions LoRA: JevBench / typed-decisions | **.779 / .622 (behind DeskMind)** | DeskMind brain-4b .831 / .658 | lead, Mac. `training/decisions/results.md` reports .801 / .6645 on Tinker; the lead's Mac numbers are the ones quoted |
| Memory follow-ups, frozen holdout half of `evals/memory_followups.jsonl` (97 sequences, 261 turns): resolution / false-rewrite | **rules + long-term (serving): .574 (all categories) / .0195** | none 0 / 0; rules .507 (non-long-term categories) / .0195; rules + LLM rewrite .634 / .078; rules + LLM + long-term .670 / .078 | `runs/memory_eval/20261024T171119-171153`, `evals/memory_eval.py` |
| Memory ship rule (pre-registered: resolution >= .85, false-rewrite <= .02) | **not met by any mode**; serving = rules + long-term, LLM rewrite off (lowest false-rewrite) | - | lead |
| Receipt OCR (Apple Vision, warm) | ~150 ms per receipt | - | `pitch/claims.md` §1 |
| Live suite (`evals/live_t1.jsonl`), earlier serving config: it2 + no-think 4B planner (before it3 / thinking / memory), runner defaults, screen unlocked; 27 of 43 cases ran | T1 **19/22 (86.4%)**, T2 1/5; files category 2/7 | - | lead; `runs/bench/live/20261024T161427Z` |
| Live suite: false_done / confirms asked | 4 / 3 | - | same |
| Live suite latency: first action p50 / p95; verified completion p50 / p95 | 193 / 812 ms; 704 ms / 4.1 s | - | same |
| HobbyLM sealed-r4 (125 tasks), it2 | **no valid comparable score yet** (the morning replay hit a harness bug and is not quoted) | HobbyLM-1B published 90/125 (their harness) | `bench/hobbylm/replay.py`; §3.7 |
| DeskMind Bench diag-v27 (13 x 3), zh-Hans | TBD(DeskMind diag, Muselet) | TBD(DeskMind diag same-Mac rerun); published 39/39 (other harness version, not comparable) | `bench/deskmind/run_muselet.py`; §3.7 |

Results not quoted anywhere (invalid): any live/HobbyLM run gathered with the screen locked; the morning HobbyLM
replay that hit a harness bug; any router r1/r2 number on a sealed external set (training near-duplicates); the 37
route_v1 cases with near-duplicates in training data. The live run above skipped 16 of 43 cases under runner
defaults (manual / pending / online / `requires_user_ok` / precondition skips; per-case reasons are in that run
dir's results file, TBD(skip breakdown from `runs/bench/live/20261024T161427Z`)).

Planner speed was measured on the earlier tuned config (tune .84 / holdout .57) and has not been re-measured for
the shipped prompt.

## 5. Honest gaps
- **DeskMind leads the System One benchmarks today:** brain-4b .831 / .658 (JevBench / typed-decisions) vs our
  decisions LoRA .779 / .622 (lead, Mac); we are behind on both. Base model: .719 / .569. Even DeskMind's 0.8B edges our base 4B on JevBench (.723 vs .719); we are ahead of
  it only on typed-decisions (.569 vs .540). Decontamination left only 301 code-gold states (no counting, multi-hop or
  long-policy), and the hard JevBench tier is where the LoRA loses (`training/decisions/results.md`).
- **HobbyLM has no valid comparable score yet**, and DeskMind Bench is not run: a harness bug blocked the morning
  replay, and that run is not quoted. The only competitor-benchmark numbers we have are the decision benchmarks above,
  where we are behind.
- **Live suite is weak on multi-step and files:** T2 1/5 and files 2/7, with 4 false_done (the agent said done but
  the final-state check failed). Only 27 of the 43 cases ran under runner defaults.
- **The big planner costs time:** the LoRA 4B plans at ~0.3 s per step, but browser / open-ended / blind turns run on
  35B-A3B with think 512 (6.0 s step p50 on the offline bench, earlier prompt), above the 3 s gate that applies to the
  normal planner. v2-holdout is the weakest planner set (.692 LoRA).
- **No end-to-end number for the shipping build:** the agentic-apps path, the 35B blind planner and the browser flow
  have unit tests (`ml/tests/`) and manual Mac checks, but no live-suite run; the live numbers in §4 are from the
  earlier it2 + no-think configuration.
- **Router it3 missed its pre-registered rule** on route_v1_clean (.922 vs it2 .942, -2.0 pt; rule allowed -1 pt);
  it serves by the user's call for route_v2 (.945 vs .838) and calibration.
- **Memory misses its ship rule** (.574 resolution vs .85 target); follow-ups beyond the rule patterns are often not resolved.
- **Planner holdouts trail tune** (.643 / .667 vs .88, no-think); the holdout numbers are the honest ones. 35B-A3B is better on
  holdout (.71) but about 2x slower per turn.
- **Router weak spots** on it2 val: compose_email .720, media_control .800, open_folder .800, set_brightness .808.
- **Not yet measured:** route p95, memory / disk footprint, grounding on the
  full ScreenSpot-Pro or OSWorld-G.
- **Safety is scoped, not universal:** Enter/Send gating covers recognized chat composers, and "done" needs a passing
  `expect` or fresh observation but there is no universal goal check (`pitch/claims.md` §2).

## 5b. Incidents and fixes
- **Spotify playlist removed (live testing on the user's Mac).** A grounded pixel click (`click "<description>"` ->
  eyes-4b) in Spotify landed on the wrong control and removed a playlist from the user's library: real user data,
  outside any test fixture. Fixes: grounded clicks are refused in Spotify outright, and the app hint and
  few-shot no longer suggest them (commit dc7a063); in every app holding user data (Music, Photos, Mail, Messages,
  Finder, System Settings, Notes, Calendar, Reminders, Contacts) a grounded click is refused (`blind_click_blocked`)
  unless OCR at the target contains the goal's subject and no destructive word such as remove / delete / library /
  trash (`_NO_BLIND_CLICK_APPS`, `_grounded_click_gate` in `orchestrator.py`); planner AppleScript that clicks or
  presses UI needs confirmation. Tests: `ml/tests/test_agentic_loop.py`.
- **TextEdit autosave (Sat).** A manual end-to-end run typed into a user's open TextEdit document and autosave wrote it
  to disk. Fix: live cases run only through the runner that enforces each case's precondition and skips when user
  documents are open (`AGENTS.md` live-test safety, §3.6).
- **Brain froze on a lazy grounder download.** A 3 GB Hugging Face download started mid-request and the brain stopped
  responding (Spotify / YouTube / Amazon tasks "kept thinking"). Fix: serving loads the local eyes-4b MLX copy and
  never downloads during a request (commit fe2de69).

## 6. Capabilities we test

| Capability | How it runs | Where it is tested |
|---|---|---|
| System skills (volume, brightness, dark mode, Wi-Fi, Bluetooth, apps, files, URLs) | router -> native HandsKit skill (26 `kind: system` in `skills/catalog.json`), skill HUD | live_t1 T1 (system 11, apps 4, files 4, time 4, ...), route_v1 |
| Agentic apps (Clock timers, Reminders, Calendar, Notes, Messages, Mail/Gmail replies, Music, Premiere) | router picks the `kind: app` skill -> planner operates the app over AX with an app hint and `finish.app_finish`; evidence ends the task | `ml/tests/` (agentic, finish, app-knowhow tests); live check pending |
| Browser via AX | planner over the AX tree incl. web content (Chrome / Safari / Zen, `HandsKit/WebAX.swift`) | live `t2-safari-flights`, `t2-answer-web`; planner bench browser scenarios |
| Finance review | `finance_review` brain tool: categorize, duplicates, receipts via OCR, over-budget; `Decimal` math | live `t2-finance-dupes`, `t2-numbers-sum`; `ml/tests/` |
| Advisor prep | `advisor_prep` brain tool -> brief in Notes; numbers computed by code | live `t2-advisor-prep`; `ml/tests/test_tool_advisor_prep.py` |
| Premiere shortcuts | `premiere_command` -> cmd+k / m / cmd+m (UXP bridge untested) | route_v1 / val label `premiere_command` |
| Grounded clicks | `click "<description>"` -> eyes-4b on a fresh <= 1 MP screenshot, two-stage zoom | ScreenSpot-Pro subset; `ml/tests/test_grounder.py` |
| Compound commands | `_compound` splits clauses; every clause must route at p >= 0.75, else the planner (`orchestrator.py:296,699`) | live `t2-two-settings` |
| Messaging with confirmation | `send_message` is `risk: confirm`; send keys gated in chat composers (`ml/src/brain/sendgate.py`) | live `confirm-no-send` (reply no -> nothing sent), `file-trash-yes/no`, `refuse-wipe`; planner `h2-send-confirm` |
| Drafting | `compose_email` creates a Mail draft (sending needs confirmation); `type_text`, `new_note` | route_v1; live `t2-textedit-write` |
