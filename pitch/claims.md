# Claims registry

Every number in `pitch/` is a `{{placeholder}}` defined here. Fill it only from the named source; if the source
has not been run, the line stays out of the pitch. Mac = the demo MacBook Pro M5 Pro, 64 GB, macOS 27
(AGENTS.md). Code citations: `origin/main` @ 1d49478.

## 1. Metrics (measure on the Mac, record the run path next to the value)

| Placeholder | Definition | How to measure | Source of truth | Value (2026-10-24) |
|---|---|---|---|---|
| `{{stt_ms_p50}}` | Right Option release -> final transcript, median | 20 demo utterances; panel row "Last release → text" | `model.lastSTTms`, `app/Sources/MuseletApp/Panel/PanelView.swift:90`; app FileLog | pending live run (screen was locked overnight) |
| `{{route_ms_p50}}`, `{{route_ms_p95}}` | Router forward pass (cached static prefix + request suffix) | `uv run --project ml python -m brain.cli eval-route --model <router> --cases evals/route_v1.jsonl` | `route_ms`, `ml/src/brain/decision.py:330-350`; `runs/evals/` | p50 52 ms (r2; `runs/router/r2_self_clean.json`); p95 not reported yet |
| `{{route_acc}}` | Router top-1 accuracy, route_v1 clean subset (103 of 140 cases) | same command, `--cases evals/route_v1_clean.jsonl` | `runs/router/r2_self_clean.json` | .864 (r2; see §1a) |
| `{{args_ms_p50}}` | ARGS extraction, median | same run / traces | `args_ms`, `decision.py:369-404` | 97 ms (r2; `runs/router/r2_self_clean.json`) |
| `{{instant_e2e_ms_p50}}` | Release -> first HandsKit action for single-skill commands | traces of the segment-1 commands, 10 takes | `release_to_first_action_ms`, `ml/src/brain/orchestrator.py:295,300` | pending live run (screen was locked overnight) |
| `{{browser_task_s}}` | "Find flights to Tokyo next Friday": release -> planner `done` | 5 takes, Chrome | trace `total` stage; also shown as the `ui.ms` chip | pending live run (screen was locked overnight) |
| `{{live_t1_pass}}`/43, `{{live_false_done}}` | Live suite T1/T2 strict pass; runs where the agent said done but the final state check failed | `bench/live/run_live.py` on `evals/live_t1.jsonl`, designated Mac | runner output under `runs/` | 2026-10-24, serving config (router it2 + tuned 4B planner, runner defaults, screen unlocked): T1 19/22 (86.4%), T2 1/5, false_done 4 (`runs/bench/live/20261024T161427Z`); 27 of 43 cases ran |
| `{{planner_tok_s}}`, `{{planner_model}}` | Planner decode tok/s and the model picked | `bench/speed_lab.py --models <repo>` shape `plan` | `runs/speedlab/results.jsonl` | 83 tok/s, Qwen3.5-4B-4bit (`runs/planner_offline/`); model pick not yet reported |
| `{{browser_task_s}}` | Utterance -> verified final state, segment 2 | traces, 5 takes, median | `runs/traces/` `total_ms` | pending live run (screen was locked overnight) |
| `{{advisor_prep_s}}` | "Prep me for the Hendersons" -> final say, DEMO.md success checks pass | 5 takes | `runs/traces/` `total` stage; target <= 30 s (`cloud/tools_interface.md`) | pending live run (screen was locked overnight) |
| `{{receipts_s}}` | "Reconcile my receipts" -> sheet flagged | 5 takes | `runs/traces/` | pending live run (screen was locked overnight) |
| `{{premiere_s}}` | Cut + marker + export dialog | 5 takes | `runs/traces/` | pending live run (screen was locked overnight) |
| `{{receipt_ocr_ms}}` | Apple Vision OCR per receipt | `ocr` RPC `ms` field | `app/Sources/HandsKit/OCR.swift:137` | ~150 ms per receipt, warm (run path not given) |
| `{{cat_rule_acc}}`, `{{cat_ask_rows}}` | Finance categorize accuracy with rules only; rows escalated to ASK | `PYTHONPATH=ml/src python3 -m pytest ml/tests/test_finance.py -s` | `ml/src/brain/finance/categorize.py` | not run yet |
| `{{hobby_muselet_pass}}`/125, `{{hobby_muselet_p50_s}}` | Muselet (router it2 only, §1b) on HobbyLM's 125 sealed-r4 live requests, strict final-state grading | `bench/hobbylm/replay.py --system muselet --round r4` | `runs/bench/hobbylm/` | pending (morning replay blocked by a harness bug) |
| `{{hobby_rerun_pass}}`/125, `{{hobby_rerun_p50_s}}` | HobbyLM itself, same Mac, its published harness | `bench/hobbylm/replay.py --system hobbylm --round r4` | same | pending (morning replay blocked by a harness bug) |
| `{{dm_muselet_strict}}`/39, `{{dm_muselet_false_done}}`, `{{dm_muselet_step_p50_s}}` | Muselet (router it2 only, §1b) on DeskMind Bench `diag` (13 tasks x 3), graded by `deskmind-bench score` | `bench/deskmind/README.md` (c) | `runs/bench/deskmind/` | pending (morning replay blocked by a harness bug) |
| `{{dm_rerun_strict}}`/39, `{{dm_rerun_step_p50_s}}` | DeskMind G18b on the same Mac, their commands | `bench/deskmind/README.md` (a) | same | pending (morning replay blocked by a harness bug) |
| `{{act_ms_p50}}` | HandsKit act + settle, median | same traces as `{{instant_e2e_ms_p50}}` | `act_ms` + `settle_ms` in `rpc_result` | pending live run (screen was locked overnight) |
| `{{stt_budget_ms}}`, `{{args_budget_ms}}`, `{{act_budget_ms}}`, `{{e2e_budget_ms}}` | Latency *targets* (not measurements); label "target" wherever shown | set by the lead from the speed-lab results | `architecture.md` budget table | targets, not set yet |
| `{{model_disk_gb}}`, `{{peak_ram_gb}}` | Total local weights; peak RSS during the 3:00 demo | `du -sh` on the HF cache snapshots in use; Activity Monitor / `footprint` | Mac | pending live run (screen was locked overnight) |
| `{{tinker_usd}}` | Tinker spend, month to date | `python3 tools/tinker_spend.py` | `runs/tinker_spend.jsonl` | $34.60 month to date (billing through 09:00Z) |
| `{{train_examples}}` | Router training examples after dedup | data-pipeline output stats | PR #2 (`cloud/data-pipeline`) | not reported yet |
| `{{outbound_conns}}` | Non-loopback sockets opened by brain + app during the Wi-Fi-off take | `lsof -nP -i -a -p <brain pid>,<app pid>` before/after; expect only 127.0.0.1:8765/8766 | Mac | pending live run (screen was locked overnight) |

## 1a. Offline benchmark results (Mac, 2026-10-24)

Values as reported from the Mac runs, with their source paths. `runs/` is gitignored, so those files live only on
the Mac. Same Mac, same runners for every row in a table.

**Router**: trained 4B LoRA "r2" (`jonsnov/muselet-route-4b-main-mlx4` @ 2e3e7bf) vs base Qwen3.5-4B, on the
route_v1 clean subset (`evals/route_v1_clean.jsonl`). Source: `runs/router/r2_self_clean.json`,
`runs/router/base_clean.json`.

| | Route acc | Macro-F1 | ARGS exact | Route + ARGS |
|---|---|---|---|---|
| r2 | .864 | .866 | 36/36 | .857 |
| Base Qwen3.5-4B | .767 | .825 | .784 | .690 |

r2 latency p50: route 52 ms, ARGS 97 ms. Always disclose: 37 of the 140 route_v1 cases were excluded because they
have a near-duplicate in training (§1b).

**Planner**: Qwen3.5-4B-4bit, greedy, few-shot + DSL history + line-start constraint; offline planner bench
(`evals/planner_offline.py`, 25 tune + 14 holdout + 12 holdout2 scenarios, runtime-equivalent grading). Source:
`runs/planner_offline/`. holdout2 was written after holdout-1 was used to derive prompt rules 16-18.

| Config | Pass (tune) | Pass (holdout) | Pass (holdout2) | Plan p50 / turn | TTFT | Decode |
|---|---|---|---|---|---|---|
| Qwen3.5-4B-4bit, shipped (rules 16-18) | .88 | .643 | .667 | 139 ms\* | 72 ms\* | 83 tok/s\* |
| Qwen3.5-4B-4bit, base config | .68 | .50 | – | – | – | – |
| Qwen3.6-35B-A3B | .84 | .71 | – | ~310 ms | 128 ms | 82 tok/s |

\* Speed measured on the earlier tuned config (tune .84 / holdout .57); not re-measured for the shipped prompt.

Say holdout alongside tune; the holdout set is the honest number.

**Live suite** (`bench/live/run_live.py` on `evals/live_t1.jsonl`, serving config: router it2 + tuned 4B planner,
runner defaults, screen unlocked). Source: `runs/bench/live/20261024T161427Z`. 27 of the 43 cases ran under runner defaults.

| T1 strict | T2 strict | false_done | Confirms asked | First action p50 / p95 | Verified p50 / p95 |
|---|---|---|---|---|---|
| 19/22 (86.4%) | 1/5 | 4 | 3 | 193 / 812 ms | 704 ms / 4.1 s |

Weakest category: files, 2/7. Quote T1 and T2 separately, with the case counts; HobbyLM r4 and DeskMind Bench are
still pending.

**System One decision benchmarks** (`bench/run_jevbench.sh`, `bench/run_typed_decisions.sh`):

| | JevBench public | Typed-decisions test |
|---|---|---|
| Muselet base | .719 | .569 |
| DeskMind brain-4b | .831 | .658 |
| DeskMind brain-0.8b | .723 | .540 |

DeskMind leads here today. Allowed: "On decision benchmarks DeskMind's 4B is ahead of our base model today; our
generalist decision LoRA is still training." Not allowed: any framing that Muselet wins or ties these.

**Grounding** (ScreenSpot-Pro, 200-sample stratified subset, paired; `bench/grounding/run_screenspot.py`, run path
not given): eyes-4b two-stage zoom 63.5% at 1 MP, 67.5% at 2 MP (no zoom: 36.0% / 50.5%).

## 1b. Contamination disclosures (review decisions-21)

Source: cloud A's overlap check on PR #2 (`cloud/data-pipeline`),
`training/reports/evalcheck/{main_report_v2,it2_report_v2,clean_subsets}.json` @ 0ce9ea6 and
`training/reports/evalcheck/external_affected_it2.json` @ 735686f (it2 datums exactly as trained, per id): router
training rows vs each eval set, rule `short_edit1` (token edit distance <= 1 when either side has <= 5 tokens).
Policy: `AGENTS.md:37-41`. "main-final" = the training data behind r1/r2; it2 = the serving router (`tools/serve_brain.sh:3`).

| Eval set | Cases | Affected, main-final (r1/r2) | Affected, it2 | How we quote it |
|---|---|---|---|---|
| route_v1 | 140 | 37 | 7 (all among the 37) | only on `evals/route_v1_clean.jsonl`: 103 cases, clean for both; say "37 of 140 excluded for short near-duplicates" |
| live_t1 | 43 | 10 | 0 | it2 only |
| HobbyLM sealed-r4 | 125 | 15 | 0 (all 125 ids checked) | it2 only; pending (morning replay blocked by a harness bug) |
| HobbyLM sealed-r1 / r2 / r3 | 95 / 95 / 107 | 12 / 13 / 10 | 0 / 1 (A04) / 1 (D09) | not quoted |
| DeskMind Bench `diag` | 13 tasks | 1 (not re-traced) | 0 real; the check reports 1 (G07-finder-newfolder), a normalizer artifact (below) | it2 only; pending (morning replay blocked by a harness bug) |
| DeskMind `dyn` | 64 | 16 (not re-traced) | 0 real; the check reports 16, the same artifact | not in the pinned comparison; not quoted |

DeskMind artifact: `norm()` (`training/src/muselet_train/decontam.py:26` on PR #2) keeps only `[a-z0-9']` characters, and
DeskMind's tasks are written in Chinese (98 of the 99 DeskMind items checked contain CJK). G07 normalizes to
"archive" and the 16 `dyn` ids to an empty string; each is one token edit from the training row "unmute", which
trips `short_edit1`. The as-trained it2 rows contain 0 CJK/kana/hangul characters (0 of 65,697), so they share no
Chinese task text with DeskMind.

Rules:
- it2 has 0 real overlaps with HobbyLM sealed-r4 and DeskMind Bench. Its only external near-duplicates are HobbyLM
  sealed-r2 A04 and sealed-r3 D09.
- Never quote any sealed-set number (HobbyLM sealed r1-r4, DeskMind Bench) from r1/r2 (main-final data has 12-15
  near-duplicates per HobbyLM sealed round).
- The §1a router table is r2 on the route_v1 clean subset only; it is not the serving router (it2).
- it2b (0 overlaps on every set, `training/reports/phase1_it2.md:292` on PR #2) is not the serving router.

Fixture facts (deterministic, already in the repo; quote freely): Henderson numbers in
`evals/fixtures/advisor/DEMO.md` ("Numbers the presenter can quote"); finance story numbers and receipt statuses in
`evals/fixtures/finance/README.md`; tool bubbles/says from `ml/tests/test_tool_advisor_prep.py:128-138` and
`ml/src/brain/tools/finance_review.py:165-196`.

## 2. Qualitative claims -> code path

Re-verified on `origin/main` @ 1d49478 (2026-10-24); line numbers are at that commit. `orchestrator.py` =
`ml/src/brain/orchestrator.py`. **Status**: `main` = true on main, say it as written; `partial` = say only the
"allowed" wording; `not built` = do not say it.

| Claim | Why it is true | Status |
|---|---|---|
| Hold Right Option to talk | listen-only CGEventTap on keycode 61, `app/Sources/MuseletApp/Voice/PushToTalkMonitor.swift:10,55-56,99` | main |
| STT runs on the Neural Engine | FluidAudio Parakeet TDT v2 (Core ML, ANE), `MuseletApp/Voice/Transcriber.swift:25-28`; fallback Apple `SpeechTranscriber`, `Transcriber.swift:68-78` | main |
| Models load from disk only | `snapshot_download(repo, local_files_only=True)`, `ml/src/brain/cli.py:32`; MLX inference, `ml/src/brain/decision.py:15-16` | main |
| Brain is loopback-only | WebSocket on `127.0.0.1:8765`, `ml/src/brain/server.py:1,15`; Premiere bridge `ws://127.0.0.1:8766`, `premiere/README.md:10` | main |
| Offline state is recorded | `online` from NWPathMonitor at key-down, `app/Sources/HandsKit/UtteranceCtx.swift:26,147` | main |
| Wi-Fi off by voice, with a HUD | `setWifi` -> `networksetup -setairportpower`, `HandsKit/Skills.swift:780-795`; HUD `wifi.slash` symbol, `MuseletApp/Overlay/SkillHUD.swift:179-181` | main |
| Skill HUD for system skills | volume, brightness, dark mode, Wi-Fi, Bluetooth; shown 1.5 s, `SkillHUD.swift:5,15,176-182`; events from `HandsKit/SkillFeedback.swift` | main |
| Accessibility tree first, screenshots only when needed | planner observes AX each turn (`orchestrator.py:951-954,1261-1266`); pixel `click` rejected without a screenshot (`orchestrator.py:784-786`); screenshots capped at `maxPixels`, own windows excluded (`HandsKit/Screenshot.swift:62,132`) | main |
| Reads web pages through AX (Chrome, Safari, Zen) | Chromium `AXManualAccessibility`/`AXEnhancedUserInterface`, WebKit and Gecko (Firefox, Zen), `HandsKit/WebAX.swift:9-15` | main |
| Doesn't type into nothing | `type` with no text target -> `no_text_target`, nothing typed, `HandsKit/Act.swift:36,544` | main |
| One forward pass routes a request | option probabilities after a cached static prefix, `decision.py:346,390-410` | main |
| Asks when a request is ambiguous | router `ASK` -> "What did you mean?" / "What <arg> should I use?" (`orchestrator.py:1116-1127`); missing slot -> question (`orchestrator.py:514-524`); planner `ask` (`orchestrator.py:709-712`); finance categorize below 0.6 -> `ask` (`finance/categorize.py:18,145-148`) | main |
| Low confidence does not act blindly | router `p_top < tau` (default 0.55) -> planner with hint "A or B" (`orchestrator.py:171,364-367`) | main. Don't say "it asks 'Did you mean A or B?'" |
| Asks for help instead of looping | same action failing twice or 3 failed turns -> "I'm stuck on that, can you help?" (`orchestrator.py:1093-1104`) | main |
| Confirms before risky actions it recognizes | `risk: confirm`/`confirm_if_unsaved` skills (send_message, compose_email, move_to_trash, empty_trash, quit_app; `skills/catalog.json`) -> `ask_confirm` (`orchestrator.py:748-755,1414-1425`); shell always; AppleScript/JXA confirm unless every target is allowlisted and no blocked pattern matches; blocked patterns include `click`, `perform action`, `AXPress`, `keystroke`, `do JavaScript`, `open location`, `«event`, `do shell script` (`orchestrator.py:872-912`, called at `:763,1379`); `press`/`type … enter` on send/delete/buy/pay/post labels, `cmd+delete`, Enter in Messages/Mail/Slack (`orchestrator.py:788-810`); one confirm unlocks only the next risky action (`orchestrator.py:713-722,822-825`); the model can't self-confirm (`orchestrator.py:738`) | **partial**. Allowed: "confirms before sending, deleting, buying, shell scripts and scripts that click or run code". Not allowed: "every irreversible action is confirmed". evals-safety-2 is resolved (all five probes confirm); evals-safety-6 is open (Enter/Send in other chat apps isn't gated) |
| Steps are checked against the live UI | an action with `expect` gets a `verify` RPC; a failed check stops the batch and replans (`orchestrator.py:856-870`) | main |
| "Done" needs evidence | planner `done` must be alone in its batch and follow a passing `expect` or a fresh observation, else it's rejected and replanned (`orchestrator.py:1076-1090`); a direct batch whose last act had no passing `expect` ends `unverified`, not success (`orchestrator.py:1303-1327`) | **partial**. Allowed: "it won't call a task done without a passing check or a fresh look at the screen". Not allowed: "done is verified by the harness", "never trusts the model's done". evals-safety-11 open: no harness-side goal check |
| Benchmarks are graded by final state | live suite graded "by final state, never by what the agent said" (`evals/live_t1.md:3-4`); `bench/live/run_live.py:292` (`strict_pass`), `pass^3` only for all-3 strict passes (`bench/live/README.md:67-68`) | main |
| Every finance/advisor number is computed by code | `Decimal` engines `ml/src/brain/finance/`, `ml/src/brain/advisor/`; model phrasing with digits/`$`/`%` rejected (`advisor/brief.py:11,37`); bubbles carry no `$` (`ml/tests/test_tool_advisor_prep.py:139`) | main |
| Every flag carries evidence | `finance/evidence.py`; advisor `evidence` lists (`evals/fixtures/advisor/README.md`) | main |
| Ghost cursor flies to the target first | 120-220 ms flight (`MuseletApp/Overlay/GhostCursor.swift:69`); for skills too, to the Dock icon / menu extra within 120 ms (`HandsKit/RPC.swift:95-104`, `HandsKit/SkillTargets.swift`) | main |
| Planner starts acting while still decoding | each streamed line is parsed and executed before the batch ends, 12 turns / 60 s (`orchestrator.py:914-918,1011-1044`) | main |
| Whole workflows run from one router pick | `executor: brain` skills `finance_review`, `advisor_prep` (`skills/catalog.json`) -> `brain.tools.run` (`ml/src/brain/tools/__init__.py:1-3,22-24`, `orchestrator.py:319-326`); tools `ml/src/brain/tools/{advisor_prep,finance_review}.py` | main |
| Receipts are read on-device | `ocr` RPC = Apple Vision `.accurate` (`HandsKit/OCR.swift:31,137`); `finance_review` OCRs all receipts concurrently (`tools/finance_review.py:157`) | main |
| Premiere cut/marker/export | `premiere_command` -> default shortcuts cmd+k / m / cmd+m (`HandsKit/Skills.swift:257-258,757`); export opens the Export dialog | main (shortcuts); UXP bridge UNTESTED (`premiere/README.md:3`) |
| Latency chip next to the bubble | brain puts `ms` on the final `ui` (`orchestrator.py:1280-1288`, `server.py:184-186`): release-to-first-action for skills, total otherwise; app shows it for 2 s (`MuseletApp/App/AppDelegate.swift:132`, `MuseletApp/Mascot/MascotController.swift:232-238`) | main |

## 3. Competitor facts (verified 2026-10-24 from the URL)

| Who | Fact we may quote | URL |
|---|---|---|
| HobbyLM-1B Computer Use | 90 of 125 sealed requests completed live on macOS (72%); median 0.26 s per decision (MLX, FP32, MacBook Air); "Local by default" | https://huggingface.co/Hobbylm/hobbylm-1B-computer-use |
| DeskMind | 0.8B decides each step, hands unsure ones to a 4B, both local; ~0.5 s / ~3.6 s median decision | https://github.com/deskmind-ai/deskmind |
| DeskMind Bench | 13 tasks on Finder, TextEdit, Safari; 13 x 3 runs, strict pass; G18b router 39/39, 0 false DONE, step p50 2.85 s (through the app, p95 9.82 s), Apple M4 Pro, zh-Hans locale | https://github.com/deskmind-ai/bench |
| Savvy Intelligence | Financial Planning Agent; "Know Your Household": meeting prep, live; Roth conversion modeling; "Every AI model provider we work with operates under zero data retention"; available to advisors who join Savvy Wealth | https://www.savvywealth.com/savvy-intelligence |
| Clicky | MIT; needs Anthropic, AssemblyAI and ElevenLabs keys behind a Cloudflare Worker; push-to-talk streams audio to AssemblyAI, sends transcript + screenshot to Claude; cursor flies via `[POINT:x,y:label:screenN]` tags | https://github.com/farzaa/clicky (README, CLAUDE.md) |

Not verified, do not say: that Savvy flags tax-loss harvesting or cash drag (not on the page); that Clicky
cannot click; any DeskMind Bench or HobbyLM live-set number on our Mac until those reruns exist (pending:
the morning replay was blocked by a harness bug; router it2 only, §1b). The JevBench and typed-decisions reruns in §1a do exist.

## 4. Demo prerequisites (open items the script depends on)

1. evals-safety-6 and -11 are open: on stage and in Q&A use only the "allowed" wording in §2.
2. Advisor bubble: `evals/fixtures/advisor/DEMO.md` says "Four opportunities"; the tool test says
   "5 opportunities found. Brief is in Notes." (`ml/tests/test_tool_advisor_prep.py:138`). Read the real bubble.
3. Receipt bubble "6 receipts match, 1 receipt mismatch, 1 unmatched." is what `summary_sentence`
   (`tools/finance_review.py:165-196`) builds for the fixture; no test asserts that exact case. Read the real bubble.
4. DeskMind already reports 39/39 on its own bench: we can at most tie on strict pass. Pitch speed and breadth,
   with both systems rerun on our Mac.
5. System One: DeskMind leads on JevBench and typed decisions (§1a); use only the allowed wording there.
6. Contamination: quote competitor benchmarks only under the §1b rules; never from r1/r2.
7. Premiere: UXP bridge untested; the demo uses default shortcuts, so the demo project must use the default keymap.
