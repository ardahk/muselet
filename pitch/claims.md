# Claims registry

Every number in `pitch/` is a `{{placeholder}}` defined here. Fill it only from the named source; if the source
has not been run, the line stays out of the pitch. Mac = the demo MacBook Pro M5 Pro, 64 GB, macOS 27
(AGENTS.md). "main" / "wip/local" = the branch where the cited code lives today (2026-10-24).

## 1. Metrics (measure on the Mac, record the run path next to the value)

| Placeholder | Definition | How to measure | Source of truth |
|---|---|---|---|
| `{{stt_ms_p50}}` | Right Option release -> final transcript, median | 20 demo utterances; panel row "Last release → text" | `model.lastSTTms`, `app/Sources/MuseletApp/Panel/PanelView.swift:90`; app FileLog |
| `{{route_ms_p50}}`, `{{route_ms_p95}}` | Router forward pass (cached static prefix + request suffix) | `uv run --project ml python -m brain.cli eval-route --model <router> --cases evals/route_v1.jsonl` | `route_ms`, `ml/src/brain/decision.py:330-350`; `runs/evals/` |
| `{{route_acc}}` | Router top-1 accuracy, 140 cases | same command | `runs/evals/` |
| `{{args_ms_p50}}` | ARGS extraction, median | same run / traces | `args_ms`, `decision.py:369-404` |
| `{{instant_e2e_ms_p50}}` | Release -> first HandsKit action for single-skill commands | traces of the 3 segment-1 commands, 10 takes | `release_to_first_action_ms`, `ml/src/brain/orchestrator.py` (wip/local:157,412) |
| `{{planner_tok_s}}`, `{{planner_model}}` | Planner decode tok/s and the model picked | `bench/speed_lab.py --models <repo>` shape `plan` | `runs/speedlab/results.jsonl` |
| `{{browser_task_s}}` | Utterance -> verified final state, segment 2 | traces, 5 takes, median | `runs/traces/` `total_ms` |
| `{{advisor_prep_s}}` | "Prep me for the Hendersons" -> note verified | 5 takes, DEMO.md success checks pass | `runs/traces/`; target <= 30 s (`cloud/tools_interface.md`) |
| `{{receipts_s}}` | "Reconcile my receipts" -> sheet flagged | 5 takes | `runs/traces/` |
| `{{premiere_s}}` | Cut + marker + export dialog | 5 takes | `runs/traces/` |
| `{{receipt_ocr_ms}}` | Apple Vision OCR per receipt | `ocr` RPC `ms` field | `app/Sources/HandsKit/OCR.swift` (wip/local) |
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
`evals/fixtures/finance/README.md`.

## 2. Qualitative claims -> code path

| Claim | Why it is true | Status |
|---|---|---|
| Hold Right Option to talk | listen-only CGEventTap on keycode 61, `app/Sources/MuseletApp/Voice/PushToTalkMonitor.swift:4-8` | main |
| STT runs on the Neural Engine | FluidAudio Parakeet TDT v2 (Core ML, ANE), `Voice/Transcriber.swift:25-46`; fallback is Apple SpeechTranscriber "(on-device)", `Transcriber.swift:66-78` | main |
| Models load from disk only | `snapshot_download(repo, local_files_only=True)`, `ml/src/brain/cli.py:26-31`; MLX inference `decision.py:13,247` | main |
| Brain is loopback-only | WebSocket on `127.0.0.1:8765`, `ml/src/brain/server.py:1,15`; Premiere bridge `ws://127.0.0.1:8766` (`premiere/README.md`) | main |
| Offline state is recorded | `online` from NWPathMonitor at key-down, `app/Sources/HandsKit/UtteranceCtx.swift:15-28,68`; traced per utterance | main |
| Wi-Fi off by voice | `networksetup -setairportpower`, `app/Sources/HandsKit/Skills.swift:445-460` | main |
| Accessibility tree first, screenshots only when needed | AGENTS.md design rules; planner sees AX text (`prompts/planner_system.md` l.1); pixel `click` is rejected without a screenshot (orchestrator, wip/local:374); screenshots capped by `maxPixels`, own windows excluded (`HandsKit/Screenshot.swift:28,62`) | main + wip/local |
| One forward pass routes a request | option probabilities read after a cached static prefix, `decision.py:150-170,286-325` | main |
| Unsure -> asks, not guesses | `p_top < tau` (0.55) asks "Did you mean A or B?", `orchestrator.py:149-155`; finance categorize below 0.6 -> `ask`, `finance/categorize.py:17,131` | main |
| Irreversible actions need confirmation | catalog `risk: confirm` -> `ask_confirm`, `orchestrator.py:403-412`; risky scripts confirm, `orchestrator.py:23-43` | main |
| Every finance/advisor number is computed by code | `Decimal` engines `ml/src/brain/finance/`, `ml/src/brain/advisor/`; LLM phrasing with digits/`$`/`%` rejected, `advisor/brief.py:11`; tests to the cent `ml/tests/test_{finance,advisor}.py` | main |
| Every flag carries evidence | `finance/evidence.py`; advisor `evidence` lists (`evals/fixtures/advisor/README.md`) | main |
| Actions are verified, not trusted | `expect` predicates (`HandsKit/Expect.swift`), planner rule 13 (`prompts/planner_system.md`) | main |
| Ghost cursor flies to the target first | 120-220 ms flight, `MuseletApp/Overlay/GhostCursor.swift:69` | main |
| Planner starts acting while still decoding | stream-consume lines, `_planner_loop`, `orchestrator.py` (wip/local:482-530) | wip/local |
| Finance/advisor workflows run from one router pick | `executor: brain` in `skills/catalog.json`; dispatch `ml/src/brain/tools/__init__.py` (wip/local) | wip/local; tool modules missing (see §4) |
| Premiere cut/marker/export | `premiere_command` -> default shortcuts cmd+k / m / cmd+m, `HandsKit/Skills.swift` (wip/local:305-310) | wip/local; UXP bridge UNTESTED |

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

## 4. Demo prerequisites (the script assumes these; not on main today)

1. `wip/local` merged: planner, `brain.tools` dispatch, OCR, `premiere_command`, `release_to_first_action_ms`.
2. `brain.tools.advisor_prep` is in open PR #5 (`cloud/advisor-2`); `finance_review.py` does not exist on any
   branch yet. Until merged, the registry returns `fallback` ("That workflow is almost ready").
3. No end-to-end latency readout on screen: the panel shows only STT ms and per-RPC ms in the activity log;
   `route_ms` is trace-only. Segment 1 needs a readout (e.g. route ms in the bubble or panel).
4. Bench harness is on `cloud/bench` (no PR yet); nothing in §1 benchmark rows exists until it runs on the Mac.
5. DeskMind already reports 39/39 on its own bench: we can at most tie on strict pass. Pitch on speed and
   breadth, with both systems rerun on our Mac.
