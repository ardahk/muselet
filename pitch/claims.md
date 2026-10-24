# Claims registry

Every number in `pitch/` is a `{{placeholder}}` defined here. Fill it only from the named source; if the source
has not been run, the line stays out of the pitch. Mac = the demo MacBook Pro M5 Pro, 64 GB, macOS 27
(AGENTS.md). Code citations: `origin/main` @ d8ad966 unless a PR is named.

## 1. Metrics (measure on the Mac, record the run path next to the value)

| Placeholder | Definition | How to measure | Source of truth |
|---|---|---|---|
| `{{stt_ms_p50}}` | Right Option release -> final transcript, median | 20 demo utterances; panel row "Last release → text" | `model.lastSTTms`, `app/Sources/MuseletApp/Panel/PanelView.swift:90`; app FileLog |
| `{{route_ms_p50}}`, `{{route_ms_p95}}` | Router forward pass (cached static prefix + request suffix) | `uv run --project ml python -m brain.cli eval-route --model <router> --cases evals/route_v1.jsonl` | `route_ms`, `ml/src/brain/decision.py:330-350`; `runs/evals/` |
| `{{route_acc}}` | Router top-1 accuracy, 140 cases | same command | `runs/evals/` |
| `{{args_ms_p50}}` | ARGS extraction, median | same run / traces | `args_ms`, `decision.py:369-404` |
| `{{instant_e2e_ms_p50}}` | Release -> first HandsKit action for single-skill commands | traces of the segment-1 commands, 10 takes | `release_to_first_action_ms`, `ml/src/brain/orchestrator.py:153,421-422` |
| `{{browser_task_s}}` | "Find flights to Tokyo next Friday": release -> planner `done` | 5 takes, Chrome | trace `total` stage; shown as `ui.ms` once the chip ships |
| `{{live_t1_pass}}`/43, `{{live_false_done}}` | Live suite T1/T2 strict pass; runs where the agent said done but the final state check failed | `bench/live/run_live.py` (PR #8) on `evals/live_t1.jsonl`, designated Mac | runner output under `runs/` |
| `{{planner_tok_s}}`, `{{planner_model}}` | Planner decode tok/s and the model picked | `bench/speed_lab.py --models <repo>` shape `plan` | `runs/speedlab/results.jsonl` |
| `{{browser_task_s}}` | Utterance -> verified final state, segment 2 | traces, 5 takes, median | `runs/traces/` `total_ms` |
| `{{advisor_prep_s}}` | "Prep me for the Hendersons" -> final say, DEMO.md success checks pass | 5 takes | `runs/traces/` `total` stage; target <= 30 s (`cloud/tools_interface.md`) |
| `{{receipts_s}}` | "Reconcile my receipts" -> sheet flagged | 5 takes | `runs/traces/` |
| `{{premiere_s}}` | Cut + marker + export dialog | 5 takes | `runs/traces/` |
| `{{receipt_ocr_ms}}` | Apple Vision OCR per receipt | `ocr` RPC `ms` field | `app/Sources/HandsKit/OCR.swift:137` |
| `{{cat_rule_acc}}`, `{{cat_ask_rows}}` | Finance categorize accuracy with rules only; rows escalated to ASK | `PYTHONPATH=ml/src python3 -m pytest ml/tests/test_finance.py -s` | `ml/src/brain/finance/categorize.py` |
| `{{hobby_muselet_pass}}`/125, `{{hobby_muselet_p50_s}}` | Muselet on HobbyLM's 125 sealed live requests, strict final-state grading | `bench/hobbylm/replay.py --system muselet --round r4` | `runs/bench/hobbylm/` (harness on `cloud/bench`, not merged) |
| `{{hobby_rerun_pass}}`/125, `{{hobby_rerun_p50_s}}` | HobbyLM itself, same Mac, its published harness | `bench/hobbylm/replay.py --system hobbylm --round r4` | same |
| `{{dm_muselet_strict}}`/39, `{{dm_muselet_false_done}}`, `{{dm_muselet_step_p50_s}}` | Muselet on DeskMind Bench (13 tasks x 3), graded by `deskmind-bench score` | `bench/deskmind/README.md` (c) | `runs/bench/deskmind/` |
| `{{dm_rerun_strict}}`/39, `{{dm_rerun_step_p50_s}}` | DeskMind G18b on the same Mac, their commands | `bench/deskmind/README.md` (a) | same |
| `{{act_ms_p50}}` | HandsKit act + settle, median | same traces as `{{instant_e2e_ms_p50}}` | `act_ms` + `settle_ms` in `rpc_result` |
| `{{stt_budget_ms}}`, `{{args_budget_ms}}`, `{{act_budget_ms}}`, `{{e2e_budget_ms}}` | Latency *targets* (not measurements); label "target" wherever shown | set by the lead from the speed-lab results | `architecture.md` budget table |
| `{{model_disk_gb}}`, `{{peak_ram_gb}}` | Total local weights; peak RSS during the 3:00 demo | `du -sh` on the HF cache snapshots in use; Activity Monitor / `footprint` | Mac |
| `{{tinker_usd}}` | Total Tinker spend (router LoRA) | `python3 tools/tinker_spend.py` | `runs/tinker_spend.jsonl` |
| `{{train_examples}}` | Router training examples after dedup | data-pipeline output stats | PR #2 (`cloud/data-pipeline`) |
| `{{outbound_conns}}` | Non-loopback sockets opened by brain + app during the Wi-Fi-off take | `lsof -nP -i -a -p <brain pid>,<app pid>` before/after; expect only 127.0.0.1:8765/8766 | Mac |

Fixture facts (deterministic, already in the repo; quote freely): Henderson numbers in
`evals/fixtures/advisor/DEMO.md` ("Numbers the presenter can quote"); finance story numbers and receipt statuses in
`evals/fixtures/finance/README.md`; tool bubbles/says from the PR tests (`ml/tests/test_tool_advisor_prep.py:121-130`
PR #5, `ml/tests/test_tool_finance_review.py:196` PR #7).

## 2. Qualitative claims -> code path

Line numbers are `origin/main` @ d8ad966 (planner landed in 17a2755) unless a PR is named. **Status**: `main`
= true on main; `partial` = say only the "allowed" wording; `PR #n` = true once that PR merges.

| Claim | Why it is true | Status |
|---|---|---|
| Hold Right Option to talk | listen-only CGEventTap on keycode 61, `app/Sources/MuseletApp/Voice/PushToTalkMonitor.swift:9` | main |
| STT runs on the Neural Engine | FluidAudio Parakeet TDT v2 (Core ML, ANE), `Voice/Transcriber.swift:25-28`; fallback is Apple SpeechTranscriber, same file | main |
| Models load from disk only | `snapshot_download(repo, local_files_only=True)`, `ml/src/brain/cli.py:31`; MLX inference in `ml/src/brain/decision.py` | main |
| Brain is loopback-only | WebSocket on `127.0.0.1:8765`, `ml/src/brain/server.py:1,15`; Premiere bridge `ws://127.0.0.1:8766` (`premiere/README.md`) | main |
| Offline state is recorded | `online` from NWPathMonitor at key-down, `app/Sources/HandsKit/UtteranceCtx.swift:26,84`; traced per utterance | main |
| Wi-Fi off by voice, with a HUD | `setWifi` -> `networksetup -setairportpower`, `HandsKit/Skills.swift:817-832`; On/Off HUD, `HandsKit/SkillFeedback.swift`, `MuseletApp/Overlay/SkillHUD.swift` | main |
| Skill HUD for system skills | level bar (volume, brightness) or On/Off (dark mode, Wi-Fi, Bluetooth), fades after ~1.5 s, `SkillHUD.swift` | main |
| Accessibility tree first, screenshots only when needed | planner observes AX text each turn (`_planner_loop`, `orchestrator.py:492-516`); pixel `click` is rejected without a screenshot (`orchestrator.py:379-381`); screenshots capped at `maxPixels`, own windows excluded (`HandsKit/Screenshot.swift:62,131`) | main |
| One forward pass routes a request | option probabilities read after a cached static prefix, `decision.py:287,331-351` | main |
| Asks when a request is ambiguous | router `ASK` -> "What did you mean?" or "What <arg> should I use?" (`orchestrator.py:222,639-642`); planner `ask` (`orchestrator.py:315-318`); finance categorize below 0.6 -> `ask` (`finance/categorize.py:17`) | main |
| Low confidence does not act blindly | router `p_top < 0.55` goes to the planner with a hint "A or B" instead of executing the top skill (`orchestrator.py:196-199`) | main. Do **not** say "it asks 'Did you mean A or B?'" (that code was removed) |
| Confirms before risky actions it recognizes | `risk: confirm`/`confirm_if_unsaved` skills (send_message, compose_email, move_to_trash, empty_trash, quit_app) -> `ask_confirm` (`orchestrator.py:351-357,851-860`); `press`/`type … enter` on send/delete/buy/pay/post labels, `cmd+delete`, Enter in Messages/Mail/Slack (`orchestrator.py:252-255,383-405`); shell always, AppleScript/JXA outside a read-only allowlist (`orchestrator.py:37-44,466,824`); the model cannot self-confirm (`orchestrator.py:341`) | **partial**. Allowed: "confirms before sending, deleting, buying and running shell scripts". Not allowed: "every irreversible action is confirmed". Open: evals-safety-2 (P0: System Events click, Safari `do JavaScript`/`open location`, raw `«event»` skip confirm), evals-safety-6 |
| Steps are checked against the live UI | an action with `expect` gets a `verify` RPC; a failed check stops the batch and replans (`orchestrator.py:436-450`); planner `done` counts only alone in its batch, after a clean batch (`orchestrator.py:609-622`) | **partial**. Allowed: "steps carry expect checks against the live accessibility tree". Not allowed: "done is verified", "never trusts the model's done", "refuses to say done until the state proves it". Open: evals-safety-11 (no final-state verify; an expect-less batch then `done` succeeds) |
| Benchmarks are graded by final state | live suite graded "by final state, never by what the agent said" (`evals/live_t1.md:3-4`); bench harness (PR #8) | main / PR #8 |
| Every finance/advisor number is computed by code | `Decimal` engines `ml/src/brain/finance/`, `ml/src/brain/advisor/`; LLM phrasing with digits/`$`/`%` rejected, `advisor/brief.py:11`; tests to the cent `ml/tests/test_{finance,advisor}.py` | main |
| Every flag carries evidence | `finance/evidence.py`; advisor `evidence` lists (`evals/fixtures/advisor/README.md`) | main |
| Ghost cursor flies to the target first | 120-220 ms flight, `MuseletApp/Overlay/GhostCursor.swift:69` | main |
| Planner starts acting while still decoding | parsed lines are executed as they stream, 12 turns / 60 s, `orchestrator.py:492-600` | main |
| Whole workflows run from one router pick | `executor: brain` (`skills/catalog.json`) -> `brain.tools.run` (`ml/src/brain/tools/__init__.py`); `advisor_prep` (PR #5), `finance_review` (PR #7); missing module -> "That workflow is almost ready" (`orchestrator.py:170-172`) | PR #5, PR #7 |
| Receipts are read on-device | `ocr` RPC = Apple Vision `.accurate` (`HandsKit/OCR.swift:30-31`); `finance_review` OCRs all receipts in parallel (PR #7) | main / PR #7 |
| Premiere cut/marker/export | `premiere_command` -> default shortcuts cmd+k / m / cmd+m (`HandsKit/Skills.swift:306,790-794`); export = opens the Export dialog | main; UXP bridge UNTESTED |
| Latency chip next to the bubble | contract only: `ui` may carry `ms` (AGENTS.md, d8ad966) | **not built**: `server.ui()` has no `ms` arg and the app does not read it on any branch |

## 3. Competitor facts (verified 2026-10-24 from the URL)

| Who | Fact we may quote | URL |
|---|---|---|
| HobbyLM-1B Computer Use | 90 of 125 sealed requests completed live on macOS (72%); median 0.26 s per decision (MLX, FP32, MacBook Air); "Local by default" | https://huggingface.co/Hobbylm/hobbylm-1B-computer-use |
| DeskMind | 0.8B decides each step, hands unsure ones to a 4B, both local; ~0.5 s / ~3.6 s median decision | https://github.com/deskmind-ai/deskmind |
| DeskMind Bench | 13 tasks on Finder, TextEdit, Safari; 13 x 3 runs, strict pass; G18b router 39/39, 0 false DONE, step p50 2.85 s (through the app, p95 9.82 s), Apple M4 Pro, zh-Hans locale | https://github.com/deskmind-ai/bench |
| Savvy Intelligence | Financial Planning Agent; "Know Your Household": meeting prep, live; Roth conversion modeling; "Every AI model provider we work with operates under zero data retention"; available to advisors who join Savvy Wealth | https://www.savvywealth.com/savvy-intelligence |
| Clicky | MIT; needs Anthropic, AssemblyAI and ElevenLabs keys behind a Cloudflare Worker; push-to-talk streams audio to AssemblyAI, sends transcript + screenshot to Claude; cursor flies via `[POINT:x,y:label:screenN]` tags | https://github.com/farzaa/clicky (README, CLAUDE.md) |

Not verified, do not say: that Savvy flags tax-loss harvesting or cash drag (not on the page); that Clicky
cannot click; any DeskMind or HobbyLM number on our Mac until the reruns above exist.

## 4. Demo prerequisites (open items the script depends on)

1. Merge PR #5 (`advisor_prep`) and PR #7 (`finance_review`, `evals/fixtures/finance/setup_mac.sh`). Until
   then the router pick says "That workflow is almost ready".
2. Latency chip (`ui.ms`) is contract-only: add the `ms` field in `server.ui()`, have the brain send it on the
   final `ui`, and render it in the app. Fallback for segment 1: panel "Last release → text" + SkillHUD.
3. Bench harness is PR #8. Before quoting HobbyLM, fix evals-safety-19 (the HobbyLM rerun is scored by its own
   `completed`, Muselet by strict final state).
4. evals-safety-2/-6/-11 are open: on stage and in Q&A use only the "allowed" wording in §2.
5. Advisor bubble: `evals/fixtures/advisor/DEMO.md` says "Four opportunities"; PR #5 says
   "Brief in Notes: 5 opportunities, $332,329 total impact." (`test_tool_advisor_prep.py:130`). The script
   follows PR #5; read the real bubble on the Mac.
6. DeskMind already reports 39/39 on its own bench: we can at most tie on strict pass. Pitch speed and breadth,
   with both systems rerun on our Mac.
7. Premiere: UXP bridge untested; the demo uses default shortcuts, so the demo project must use the default keymap.
