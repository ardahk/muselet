# hands — digest (Pass 97)

Open: 0 P0, 7 P1, 21 P2.

Ranked open P0/P1:
-1. P1 hands-38 (main e2f7e5e via a615f00, ClockAX.swift:523-552): the Clock cancel falls back to `live.first` and presses a stale detail-pane Cancel after a fixed 80 ms. It can cancel a user's own Clock timer and still report success. Fix before the demo.
0. P1 hands-36 (main e425cad via #86, ClockAX.swift:546-708): the Clock wheel key fallback clicks the wheel, then types digits and up to 70 HID arrow keys without re-checking Clock is frontmost or the wheel has focus. Keys can land in the user's frontmost app. Gate it before the demo.
1. P1 hands-34 (main cf33215, Launch.swift:224-232; browser-flow merged, so planner url steps use it too): fix-same-tab merged unchanged. Same-tab open_url/web_search posts cmd+L, waits a fixed 80 ms, then types the URL plus Return without checking the address bar has focus. The brain uses it by default whenever a browser is frontmost; cloud/browser-flow c0421e6 also sends every later planner `url` step in a task through it (pass 76).
2. P1 hands-29 (main, ClockAX.swift): Clock start and cancel bring Clock to the front and never switch back, and there's no opt-out.
3. P1 hands-26 (main, orchestrator.py:3051): the brain removes `expect` from `act`, so the app's built-in polling never runs.

Next moves (max 5):
1. hands-34: poll for the address-bar focus (2 stable samples, <= 0.5 s) before typing; otherwise fall back to a new tab.
2. hands-29: record the frontmost pid before openApp and re-activate it after Start/Cancel.
3. hands-26: send `expect` with `act` and drop the extra verify when expect_ok is present.
4. hands-35: wait for the Go-to-folder sheet before typing in the Premiere import, and fail when OCR finds no footage name.
5. hands-33: when ax.pressed, call clockAXRead() once before starting the Muselet fallback.

Pass 97 (wip/local aadf777 only; no new findings):
- The CANVAS_APPS prefix is widened from "Adobe Premiere Pro" to "Adobe Premiere" (orchestrator.py:647), so app names like "Adobe Premiere 2026" or "Adobe Premiere Pro (Beta)" variants get the canvas/blind hint. It also covers Premiere Rush/Elements, which is harmless. A test is added in test_grounder_wire. Fine.
- All open findings unchanged.

Pass 96 (main b00f679 README only; wip/local 35aed2d uncommitted on 264cc82; no new findings):
- AppResolver (Act.swift:913-965) now recursively enumerates /Applications, /System/Applications and ~/Applications. It skips package contents and hidden folders, so nested vendor bundles (Adobe Premiere Pro 2026/…app) resolve. The `apps` RPC uses the same walk. Exact names win over substrings across all roots, and substring matches are path-sorted within each root. Tests cover this (Swift, not compiled here).
  - Watch: there's no depth limit, so big non-package vendor folders are walked in full. `apps` has a 3 s RPC timeout (cached 60 s), and open_app walks it synchronously. Time `hands probe apps` once on the demo Mac. Not a finding yet.
- Brain `_resolve_app` fallback strips `.app` and a trailing year ("Adobe Premiere Pro 2026"), and only takes a unique match. Fine.
- All open findings unchanged (hands-43/44/50/51 still present on heads).

Pass 95 (main d09f4d8 #130 page-load; wip/local 01a929c):
- New P2 hands-51: the firstWebArea BFS (up to 400 nodes, no deadline) runs on every observe, including non-browser apps, which always pay the full scan.
- Page-load wait on main: `_await_page_load` waits only for AXLoaded (15 s cap). AXElementBusy only extends the failed-expect re-check loop, so the pass-91 worry (every press waits 15 s on busy YouTube) is limited to failed expects.
- wip 264cc82: the Numbers tips add SORT/SORTBY formulas, which spill a copy into empty cells. Accurate, but it invites writing into cells for a "sort" request, which the integrity guard may block. hands-50 is still open (skills list).

Pass 94 (wip/local 7b8f421 only; no new findings):
- e781dc1 `_ax_ref_for_click`: a grounded `click "<target>"` becomes `press #ref` when exactly one enabled button/tab/row/etc. label matches. The match is exact and normalized, with no substring matching, and right/double clicks are excluded. It reads the last observation, so a stale ref fails rather than misclicking. Directionally good: it saves a grounder call. It dedupes by ref, so two elements sharing a ref (hands-43) count as one match and can press the wrong one.
- `_verify_done` for ui_only planners now forces screenshot+OCR (tools mode only, off by default). The privacy gate now also skips chat-IDE windows and Muselet as the push-to-talk app (good).
- The Numbers hint tips were rewritten (Organize > Sort rules), but its skills list still names finance_review/advisor_prep (hands-50 still open).

Pass 93 (wip/local 9015e83 only):
- 2900d4b rewrites planner_system rules 1/8/9/10/14/16 to be generic, removes the Safari cmd+L and Numbers SUM examples, and adds a prompt-contract test. hands-50 is partly fixed; the numbers hint's skills list still names hidden skills.
- Context screen capture now uses the current frontmost app (good). In tools mode (ui_only) the brain forces OCR on every turn with up to 2400 chars: an extra screenshot and OCR per turn, a latency cost. It's off by default.
- Rule 14 no longer tells the planner to `expect focused` before typing in document apps; the app-side no_text_target check still applies.

Pass 92 (wip/local a6035fb only; main unchanged):
- a2004d9 deletes the finance/advisor engines (-5.3k lines), following the user override in AGENTS.md. Every app/analysis intent now always goes to the agentic planner, and tools.run is a shim to _agentic_route.
- New P2 hands-50: planner_system.md rule 8 and the numbers hint still point the planner at the now-hidden skill finance_review.
- Demo risk (lead): the finance and advisor segments now depend on the 35B planner writing Numbers AppleScript live, with soft or stripped expects (hands-44). Rehearse both on the demo Mac before merging.

Pass 91 (wip/local 4db92e8 only; main unchanged):
- hands-44 status: soft-expect tasks now strip `expect` from act entirely, so the app never checks it.
- Page-load signal (e2cb384): observe returns web_loaded/web_busy from the first AXWebArea. firstWebArea is a BFS of up to 400 nodes with copySingleAttr on every observe and no deadline (latency, like hands-41). The brain now does one extra observe after every browser press, typed enter or Return, and polls up to 15 s while AXLoaded=false or AXElementBusy=true. Hypothesis, not verified: on SPAs/streaming pages (YouTube, Gmail) AXElementBusy may stay true, so each press waits the full 15 s. Worth one timing check on the demo Mac.
- Numbers sort guard (blocks AppleScript cell rewrites on sort goals): OK. Panel drops the Models section; the persisted escalate value is still sent in config. Premiere clipSpeed is now treated as hot text and shows its value (helps hands-47's readback, but the type path still doesn't verify).

Pass 90 (no new findings; 2 status updates):
- hands-44 widened: soft expects now apply to every agentic app task (36422a7).
- hands-47: the Premiere hint says one batch with no expects, so the duration edit has no check at all.
- 4bf7a41 blocks cmd+L/cmd+T in browsers unless the user asks for the address bar, and the browser tip now says use `url`. That's good for Zen, but the `url` steps now go through the same-tab path more often (hands-34 still open). The new cart-count patterns look fine.
- wip/local matches main.

Pass 89:
- New P2 hands-49: the focused text input is added to observations with no check that it is inside the observed window, and its parent walk has no deadline.
- planner sample_row (8512116): GPU argpartition top-k, then temp/top-p in numpy on the k survivors. Same distribution (only the RNG stream differs); prefill_ms/prompt_tokens added to traces. OK.
- MUSELET_NO_ESCALATE=1 (3c59fdc) makes the brain ignore the app's escalate toggle. OK; os is imported.
- wip/local matches main; cool-tasks cfbec49 only merges main. hands-43/44/46/47/48 are unchanged.

Pass 88:
- New P2 hands-47: the Adobe hot-text type path is a blind click, cmd+a and keystrokes with no edit-mode or value check.
- New P2 hands-48: the style regex rewrites short literal replies containing nice/kind/short as model-composed text.
- Observe now keeps the focused element and text inputs (up to 20) past max_nodes. Refs are assigned after the cut, so this is fine. The walk is still capped at 2x max_nodes interactive nodes, so a reply box beyond that is still missing.
- Nit: in serve_brain.sh, the `THINK=${THINK:-1024}` for a 35B --planner-model path is a no-op because THINK was set to 512 on the line before. PLANNER=35b sets 1024 earlier, so the demo path is fine.
- Premiere edits now go to the agentic planner with no parsed args. wip/local matches main; cool-tasks 2fafa9e only merges main. The other open findings are unchanged.

Pass 87 (no new findings):
- main b92677f (#121) adds the MLX worker fix. It skips futures cancelled before they start with set_running_or_notify_cancel and guards set_result/set_exception with done(). That's correct; a running future can't be cancelled, so the guard is only defensive. generic_decide gets default temperatures. Plus the README. No app/ change.
- wip/local matches main. hands-26/34/36/38/43/44/45/46 are unchanged.

Pass 86:
- New P2 hands-46: the destructive-refuse regex (93ca931) refuses 'format the entire column', 'remove all formatting', 'delete all empty rows', 'show all files' and the empty_trash phrasings before routing.
- main ca73c12 merged ui-progress (#105, uncompiled Swift, no issues found), native-tools (#108, off by default; hands-26 status added) and the step-phrase bubble (progress.py; hides secrets and text over 30 chars). The Premiere hint changed to cmd+r Speed/Duration.
- wip/local matches main apart from the README; cool-tasks 3937e6b only merges main 85958b0. hands-44 (P1) is unchanged.

Pass 85:
- main 85958b0 (#115-#117): a524768 turns a failed expect into status ok whenever a finish criterion exists, so the batch no longer stops at the first failed expect. hands-44 raised to P1. The rest is shopping few-shot/hints and the create_reminder guard (brain only). No app/ change.
- cloud/cool-tasks a77104e is a main merge plus hints; wip/local matches main.

Pass 84 (no new findings; open counts unchanged):
- main 2445a1d (#110-#114): brain hints only (shopping, maps), finish email_open criterion, and sendgate 'Ask Gmail'. The hands-45 regex widened (status record). No app/ change.
- cloud/cool-tasks e4def97 and wip/local 6e7f50b (one hint line) are main merges or hint-only changes. hands-26/34/36/38/39/40/41/42/43/44 re-checked: unchanged.

Pass 83:
- main 4f94e42 (#103/#104/#107/#109): YouTube play evidence now requires youtube in window/url; the web_ui_guard message was changed. New P2 hands-45: a search/find label skips the Enter-send confirm even in composer apps, and enter_sends falls back to the focused element when the ref is stale. No app/ change.
- cloud/ui-progress a66166b (uncompiled Swift): the busy flag keeps the dots up until a terminal mood, with a 360 s safety net, and is cleared on disconnect, confirm and decline. No contract issue. Static only; not built.
- cloud/cool-tasks 4c84adc: the `note` op is brain-only (never sent to the app). Relay tasks refuse send actions ("draft only"). OK for the hands lane.
- cloud/native-tools 6053e4e: tool calls are converted to DSL via to_dsl, so the app contract is unchanged. Tool calls carry no expect, which widens the hands-26 gap for PLANNER_MODE=tools (default dsl).
- wip/local matches main. hands-43/44 are still on main.

Pass 82:
- main b7b38f9 merged agentic-fixes2 (hands-42 is now on main) and docs-final. ab850b3: blind/agentic tasks get 30 turns / 300 s, and planner expects there are soft. New P2 hands-44: soft expect failures `continue` before both loop guards, so a repeated side-effectful action whose expect fails is never stopped. b7b38f9: PLANNER=35b sends max_nodes 350; the app takes it as-is (RPC.swift:85), which is fine. No app/ change. hands-43 is still on main.
- wip/local matches main.

Pass 81:
- main 73b8031: observe no longer crashes on duplicate refs (uniquingKeysWith first). New P1 hands-43: the duplicates come from Differ.match pass 2, which maps every unmatched new element with the same role+label to the one old candidate. Duplicate refs now act on the first element silently, and `current` (first) disagrees with knownElements (last). That's a wrong-row risk for repeated Delete buttons.
- agentic-fixes2 104a411 is a main merge only; hands-42 stands. wip/local matches main. Other open findings unchanged.

Pass 80:
- main 3e323a9 merged #101 spotify-play and cef8797. That puts the 35B on every agentic-app and timer-control task (the wip change from pass 79, now on main), and adds PLANNER=35b. No app/ change. In Spotify, grounded `click ... double` is now allowed through `_click_target`; the blind-click OCR subject gate still applies, so I'm accepting it. Spotify play evidence runs a read-only AppleScript through the act RPC. It needs the subject in the track name, so expect some false "couldn't verify" results on vague goals.
- cloud/agentic-fixes2 b9cd089: the brain's valid_predicate (`_PRED_RE`) matches Swift Expect.parse (title~/focused/value/app/appears/gone), so dropping a predicate the app would reject is consistent. New P2 hands-42: the YouTube watch-URL evidence depends on a URL the app's observe never returns. It does nothing on the press-a-link flow, and ctx.url can make it pass on an old page.
- wip/local matches main. Re-checked hands-26/34/36/38/39/40/41: unchanged.

Pass 79 (no new findings; open counts unchanged):
- main 5d135d0 adds only the agentic-fixes2 brief. Item 2 (drop a bad expect in the brain rather than fail the act) matches the app, which rejects bad predicates before acting (Act.swift parse-up-front). No app change is needed.
- wip/local c86fec4 sets `_force_blind` for every agentic-app and timer-control task, so all Clock start, pause and cancel planning now runs on the 35B (think 512). It's reset per planner loop (orchestrator.py:4033), so it doesn't leak to the next task. This slows the demo timer step and keeps the 35B always hot (memory). It also contradicts docs-final ("other agentic-app turns stay on the LoRA").
- cloud/docs-final bf9118d: the AGENTS timers RPC text is now correct (clock_ax/muselet, no Shortcuts). Claims that rely on open findings: "Clock Pause/Resume row ends the task" (hands-39 residual), "same tab" (hands-34), demo step 3 timer and cleanup "cancel the Clock timer" (hands-40 wheel typing, hands-36, hands-38). Have the presenter cancel the timer by hand, or keep no user Clock timers on the demo Mac.
- Re-checked hands-26/34/36/38/39/40/41: unchanged on main.

Pass 78:
- main cf33215 merged #99 control-labels, obs-labels, browser-flow, agentic-evidence and app-knowhow.
- New P2 hands-40 (Act.swift:380-386, 751-789): `type` on any slider (including AXValueIndicator) arrow-keys toward the raw digits for up to 70 presses. There's no range check, it doesn't stop when it overshoots, and it returns ok whatever the read-back value is. A 0-1 slider given "50" is driven to max. Arrows bypass `events`, and there are no tests.
- New P2 hands-41 (Observe.swift:106-124, 224-235, 262-285): derived labels call copyAttrs on every sibling for each unlabeled element, with no deadline check (observe latency risk), and an unlabeled icon button can take a nearby filename as its label.
- hands-34 is now wider on main (in_task same-tab). hands-39 has narrowed: the _evidence_base gate is on main, and the timer_start and cancel evidence gaps remain.
- wip/local 11da94c matches main for app/. Cloud branches unchanged. hands-26/36/38 re-checked: still present (orchestrator.py:3495, ClockAX.swift:534).

Pass 77:
- New P2 hands-39 (main finish.py/orchestrator.py): timer auto-done treats 'no Pause/Resume visible' as cancelled and any Resume as paused. It's checked against the observation from before the batch, so 'cancel my timer' can stop after `open "Clock"`, with only the model verifier left to catch it. cloud/agentic-evidence 1918cad mostly fixes it (_evidence_base gate); its timer_start check can still match a user's own timer.
- main 3a0860c: BLIND_PLANNER now defaults to `escalate` (35B-A3B, ~19 GB, warmed at startup) whenever that model is in the HF cache. Outside this lane, but a demo memory risk next to the router, planner and eyes-4b: check kern.memorystatus_level with all of them loaded. Untracks the .venv and models symlinks. No app/ change.
- cloud/browser-flow 485763f: the web UI guard rejects planner-built same-site search URLs and typing queries into the address bar (brain only). Same-tab inside tasks is unchanged, so the hands-34 status record still applies.
- cloud/app-knowhow c69dfec: prompt tips only. wip/local 83cf584 matches main for app/. Other open findings re-checked and unchanged.

Pass 76:
- main de1070d merged agentic-apps (catalog `kind`, already cleared) and f30bf1d. The only app/ change: GhostCursor no longer shows the box highlight around the target (opacity 0, pop removed). Failures still show through the chip colour and ripple. Harmless.
- cloud/browser-flow c0421e6 (brain only): default-browser rewrite, read from the LaunchServices plist (Swift falls back to the default handler if the name doesn't resolve), and same-tab for planner `url` steps. hands-34 status record added: that widens the blind cmd+L path.
- cloud/app-knowhow fc92f6b (brain/prompts only): the Clock tips have the planner press a running timer's Pause/Cancel button, with no check that the timer is Muselet's. Same risk as hands-38, but through the planner. Noted only, no new record.
- cloud/agentic-evidence c4703c4: finish/evidence changes only, no new RPC methods or fields. wip/local 52e4b94 matches main for app/. Other open findings re-checked and unchanged.

Pass 75:
- cloud/agentic-apps 1904638 merges main (timer_control removed upstream, finish evidence gate). Against main it differs in app/ only through skills/catalog.json (`kind` keys). Swift loads the catalog with JSONSerialization as [String: Any] (Skills.swift:49), so the extra key is ignored; confirmed. No RPC changes.
- main, wip/local and the other cloud/* are unchanged. Open findings re-checked and unchanged.

Pass 74:
- main e2f7e5e merged agentic-loop (page-load re-poll, finish gate, Spotify: no pixel clicks), fix-thinking (grounder prewarm, blind_click_blocked, timer_control), premiere-route-fix, and a615f00, whose ClockAX change is identical to wip 422399a. So hands-38 (P1) is now on main.
- cloud/agentic-apps 523d2c1 (brain and catalog): adds a `kind` key to the skills/catalog.json entries. Swift reads the catalog untyped (Skills.swift:32-41), so an extra key is harmless; there are no app/ changes and no RPC changes.
- wip/local 3f8e2f8 matches main for app/. Other open findings re-checked and unchanged.

Pass 73:
- main fe2de69: serve_brain.sh now uses the local eyes-4b MLX grounder. No app/ change.
- wip/local 422399a: Clock cancel rework (live rows = rows with a pause button, detail-pane Cancel). New P1 hands-38: the `live.first` fallback and a stale Cancel index can cancel the wrong or a user-owned timer. The wip brain changes (orchestrator/finish/cli) add no new RPC methods or fields.
- Open findings re-checked; no other branch moved.

Pass 72:
- main e8023b8 merged #87 (blind planner, reviewed in pass 71) and #88 (blind typing). New P2 hands-37: TextTarget.blindTree counts an empty or not-yet-populated window as blind, so type_text keystrokes into it instead of failing no_text_target.
- cloud/agentic-loop 9b2e512 (brain only): a failed expect on a loading page re-polls `verify` every 0.25 s for up to 5 s (orchestrator.py:3315-3339, bounded, 15 s RPC timeout). This partly covers hands-26's slow-UI case for page loads, but `act` still strips `expect`, so non-page settles still get one verify.
- wip/local 20055d1 matches main. No other branch moved.

Pass 71:
- wip/local 323d274 (on local main@c711320): blind-planner rework (finish.py finish_when criteria, batch cap 2, few-shot blind examples, IDE screen-context gate). There is no app/ diff against main e425cad, and no new RPC methods or fields; expect is only read locally (_last_expect_app_only). No HandsKit contract impact.
- main and all cloud/* are unchanged. Open findings re-checked and unchanged.

Pass 70:
- main e425cad merged #86 (P0: screen-context gating, open-ended ask guard, Clock wheel keyboard fallback). Its app/ diff is identical to wip c156d18, so hands-36 (P1) and the hands-30 timeout update now apply to main.
- The brain parts of #86 (open-ended ask rejection, goal-gated screen text, timer-fallback warning) were reviewed in pass 69 and match the Skills.swift result fields.
- wip/local 80c871c is a snapshot on main@82c9810, so it no longer differs from main in app/ beyond #86. No other branch moved.

Pass 69:
- wip/local c156d18: new setClockWheelKeys fallback (click the wheel, type digits, arrow-step) when the AX set doesn't stick. New P1 hands-36: no frontmost/lock/focus gate before the HID keys. hands-30 update: the key fallback can reach about 60 s for three wheels, past the 30 s RPC timeout.
- The wip brain changes (orchestrator.py: open-ended ask rejection, timer-fallback warning log, screen text gated on goal relevance and labelled as data) are brain-side. The warning reads the clock_ax_reason/backend/clock_ax_steps fields that Skills.swift returns, so it matches.
- main and all cloud/* are unchanged since pass 68.

Pass 68:
- main 82c9810 (orchestrator.py:564-580): observation_blind now also counts an AX tree as blind when every element's label is window chrome (close/minimise/zoom/full screen). That sends CEF apps like Spotify to the screenshot and grounder path. Empty trees still count as blind (all([]) is True), and unlabeled elements don't match, so normal trees aren't affected. It is consistent with the observe contract, and app/ is unchanged.
- cloud/premiere-route-fix 7769c32: brain routing only (the Premiere pre-route now runs first, and the fallback no longer passes draft_email args to premiere_edit). No app/ change and no protocol change.
- wip/local 5b656ef matches main for app/. All open findings re-checked and unchanged; hands-34 and hands-35 are still on main.

Pass 67:
- main dc6f2f5 merged fallback, open-ended, fix-same-tab, fix-pending, hands-clock-verify, design-polish and premiere-demo.
- hands-28 is resolved: an unverified Clock start now falls back to Muselet's timer. hands-33 and hands-34 are now on main, unchanged.
- New P2 hands-35 (premiere_edit.py:336-356): the Premiere import uses fixed sleeps and blind keystrokes in the Import dialog. cmd+A plus Return can import whatever folder the dialog shows, and the OCR check never fails the tool.
- No new issues in VoiceController's confirm-forward (reviewed in pass 64), PanelView/Mascot (design-polish, pass 63) or the open-ended/fallback brain code (no app/ changes). Premiere menus are clicked through System Events, so the Window menu doesn't stay open; hands-31 is still open for the Swift skill path.
- wip/local 6a1f942 matches main for app/.

Pass 66:
- main b340f24 merged #74 memory-writes, #75 fix-apps-notes, #76 fix-email-reply, #79 test-strategy and #82 planner-aux. None of them change app/. The brain-side launch AX wait (`_wait_launch_ax`) uses bounded polling, and the webmail reply checks the draft signature before typing; neither raises a HandsKit contract issue. Replay STICKY RPC methods match the app's method names.
- wip/local 94f6fe9, cloud/open-ended fd87f69 and cloud/planner-aux 387c3b4 have no app/ changes.
- Re-checked on main: hands-26 (now at orchestrator.py:2641), hands-27 (BrainClient.swift:91) and hands-28 (Skills.swift:887) are still open. fix-same-tab, hands-clock-verify and fix-pending are not merged yet, so hands-34 and hands-33 stand on their branches.

Pass 65:
- New P1 hands-34 on cloud/fix-same-tab: blind address-bar typing. The brain makes same_tab the default whenever a browser is frontmost.
- cloud/fallback 2ef5805 and cloud/test-strategy 96c96d2 have no app/ changes. main and wip/local unchanged.

Pass 64:
- main 4150ecb only adds briefs (no app/ change); wip/local catches up to #70.
- cloud/hands-clock-verify a4d6463: verifies wheels (2 stable reads), polls 2 s after Start, retries Start once, and returns start_unverified, so startTimer falls back to Muselet's timer. This fixes hands-28 on that branch. New P2 hands-33: the fallback after Start was pressed can double-fire or leave a Clock timer that cancel can't reach.
- cloud/fix-pending dba9094: VoiceController forwards non-yes/no utterances during a confirm. server.py only runs them if confirm_interrupt sees a new command, and a cancelled ask_confirm sends confirm_cancel. Protocol matches; no issues.
- cloud/fallback, fix-apps-notes, fix-email-reply and memory-writes have no app/ changes.

Pass 63:
- main fa0f040 merged #70 (design): native Settings panel, kitten menu-bar icon, Clock-only timers (Shortcuts backend and Settings > Timers removed), mascot clamped to visibleFrame, pill hides at once with a gap-bridge zone, one close path for Esc and X. These are the cloud/design deletions, now merged on purpose and documented in AGENTS.md:149, so hands-32 is superseded.
- Brain/bench code does not read the removed `clock`/`shortcuts` fields (only bench/tests fixtures mention backend "clock").
- cloud/design-polish bf4ae64 (compact panel, kitten rect includes the tail, memory list filtered to user types) and wip/local 973a9b0: no issues. cloud/memory-writes d04e26c has no app/ changes.

Pass 62:
- No new findings. main 6a37d0c (HobbyLM calc_checker reads the macOS 27 Calculator display, bench only, outside lane) and wip/local 9571a9e have no app/ changes. hands-26 (orchestrator.py:2556), hands-27 (BrainClient.swift:91) and hands-28 (ClockAX.swift:409) re-checked on main: still open. hands-32 unchanged.

Pass 61:
- No new findings. main 13d0486 (HobbyLM replay captures calendar events in the runner, bench only) has no app/ changes; wip/local unchanged. hands-26 (orchestrator.py:2556), hands-27 (BrainClient.swift:91) and hands-28 (ClockAX.swift:409) re-checked on main: still open. hands-32 unchanged.

Pass 60:
- No new findings. main 55e38f9 (HobbyLM replay records calendar precondition errors, bench only) and wip/local fd357b3 have no app/ changes. hands-26 (orchestrator.py:2556), hands-27 (BrainClient.swift:91) and hands-28 (ClockAX.swift:409) re-checked on main: still open. hands-32 unchanged.

Pass 59:
- No new findings. main f5b4606 (bench harness frees the slot after a client disconnects; brightness tests paraphrased) and wip/local c49bf0e have no app/ changes. hands-26 (orchestrator.py:2556), hands-27 (BrainClient.swift:91) and hands-28 (ClockAX.swift:409) re-checked on main: still open. hands-32 unchanged.

Pass 58:
- No new findings. main 19d57fb (memory LLM gate #69; vague brightness asks now send set_brightness delta=±10/30) and wip/local 8a197f8 have no app/ changes. Checked the protocol for delta: argfix.vague_delta returns int, and Skills.swift:468/520 accepts `delta` as an alternative to `level` via intArg. It matches. hands-26 (orchestrator.py:2556), hands-27 (BrainClient.swift:91) and hands-28 (ClockAX.swift:409) re-checked on main: still open. hands-32 unchanged.

Pass 57:
- No new findings. wip/local 7728b98 and cloud/memory-llm-gate f6229d7 have no app/ changes; main unchanged at 9be963d. All open findings unchanged (hands-26/27/28/29/30/31/32).

Pass 56:
- No new findings. main 9be963d (memory rules #71/#72, docs-demo-3 #68, bench proxy now replaces a stale HandsKit connection instead of rejecting the new one) and wip/local 4d22445 have no app/ changes. hands-26 (orchestrator.py:2542), hands-27 (BrainClient.swift:91) and hands-28 (ClockAX.swift:409) re-checked on main: still open. hands-32 (cloud/design b93bb50) unchanged.

Pass 55:
- No new findings. Still open, P1 hands-32: cloud/design b93bb50 (unchanged) deletes main's ClockTimers.swift, SettingsView, PanelComponents, KittenAvatar and TimerSettings. Do not merge as-is.
- main e4594d9, wip/local fc5d595, cloud/memory-hotfix d932320 and cloud/memory-rules2 03c3cd1 have no app/ changes. hands-26 (orchestrator.py:2542), hands-27 (BrainClient.swift:91) and hands-28 (ClockAX.swift:409) re-checked on main: still open.
- panel-hook-fix ef35421 only touches DebugHooks, which are UI-only. docs-demo-3 and memory-llm-gate have no app/ changes.

Pass 53:
- main e9fb42d merged hands-clock (#55) and brain-9's named browsers. hands-28, hands-29 and hands-30 are now on main, unchanged (ClockAX.swift:409, :318/:424, :479). The #55 title says 'Clock in front', so hands-29 needs a lead decision: deliberate or not.
- wip/local bf98333 and brain-9 327ef2c are main merges only.
- hands-26 is still open (orchestrator.py:2542).

Pass 52:
- main 8fb465c merged ui-polish (#49, reviewed in pass 45), architect-27 (#65), memory phase 1/2, and BrainClient's ignore of the `memory` frame. That is fine for headless mode.
- hands-31 is now on main, unchanged.
- cloud/hands-clock 6ab40be was rebased onto main plus a test-fixture tweak. hands-28 is still open (ClockAX.swift:409, the unverified finish(nil)), and so is hands-29 (:318 and :424, no restore of the previous frontmost app).
- hands-26 is still open (orchestrator.py:2456).

Pass 51: main 0b83c3b and wip/local e4f4331 have no app/ changes. brain-9 and decisions only merged main's Expect scoping, which I reviewed in pass 46. memory, memory-lt, planner-verify and safety-planner28 have no app/ changes. hands-26 is still open (orchestrator.py:2101) and so is hands-27 (BrainClient.swift:91).

Pass 50: main 18c139f and cloud/planner-lora 79f0a97 have no app/ changes. hands-26 is still open (the expect strip is now at orchestrator.py:1986) and so is hands-27 (BrainClient.swift:91).

Pass 49: only cloud/decisions moved (c88b613). Its app/ is identical to main 46b97f5, so there is nothing new. Open findings are re-checked and unchanged.

Pass 48:
- main 46b97f5 has no app/ changes. hands-26 is still open (orchestrator.py:1965) and so is hands-27 (BrainClient.swift:91).
- wip/local 719907a and live-cases fa9c374 only add the Expect merge from main. brain-9 e9e9b42 and safety-brain12/18/38/planner28 have no app/ changes.
- cloud/safety-architect27 4edcba5 focuses Premiere's Timeline via the Window menu before sending shortcuts. New finding hands-31 (P2): the failure path leaves the menu open and there is no settle before the keystroke.

Pass 47:
- main a97fcba merged the w9-safety `appears` scoping I reviewed in pass 46. hands-26 is still open (the expect strip is now at orchestrator.py:1965) and hands-27 is still open (BrainClient.swift:91).
- cloud/brain-9 3f9718b adds a named `browser` to open_url and web_search (Skills, Launch) and act op=url, via SkillTargets.liveAppPath, with a fallback to the default browser and a browser_fallback flag. No issues found.
- wip/local, memory*, planner-think/verify and safety-*: no new app/ changes beyond the main merge.

Pass 46 reviewed:
- main 806b0d4 and wip/local 6b1006e have no app/ changes. hands-26 and hands-27 are re-verified open; the orchestrator.py expect strip is also present on cloud/planner-verify at line 2011.
- cloud/hands-clock 26d4427 adds ClockAX.swift, about 660 lines that drive Clock.app via AX. It is marked uncompiled.
- cloud/w9-safety 6aa332a: the `appears` matching change is word-bounded and searches only the focused window plus its sheets, popovers and open menus. That closes my "Not filed: appears substring" note. OK.
- cloud/memory-lt f0ea345: memory frames list/search/delete/clear and config.memory match its AGENTS.md. OK.
- cloud/decisions: app/ is identical to main.
- docs-demo-2, live-cases, planner-think, planner-verify, memory: no app/ changes.

Static analysis only.

Open: 0 P0, 4 P1, 7 P2.

Open P0/P1, ranked:
- P1 hands-32: cloud/design deletes merged main features (ClockTimers, Settings, KittenAvatar) (app/Sources/HandsKit/ClockTimers.swift et al.)
- P1 hands-28: an unverified Clock AX start is reported as a set timer that never fires (main app/Sources/HandsKit/ClockAX.swift:409)
- P1 hands-29: Clock AX start and cancel steal focus and never restore the prior app (main app/Sources/HandsKit/ClockAX.swift:318,424)
- P1 hands-26: the brain strips `expect` from act, so HandsKit's expect polling never runs (ml/src/brain/orchestrator.py:1896; app/Sources/HandsKit/RPC.swift:173)

Open P2: hands-31 (Premiere Timeline menu left open; now on main), hands-30 (Clock wheel stepping latency), hands-27, hands-25, hands-20, hands-16, hands-10.

Highest-leverage next moves:
1. hands-28 before merging hands-clock: an unverified start must fall back, or keep a real Muselet alarm. Otherwise users get silent missed timers.
2. hands-29: save and restore the frontmost app around the Clock AX calls, so compound utterances and the demo keep focus.
3. hands-26: pass expect inside act. That is a one-line change, fixes slow-UI expect failures, and saves one RPC plus one AX walk per action.
4. hands-30: cap clockAXStart at about 5 s and step wheels in the shorter direction.
5. hands-27: use CGDisplayBounds in BrainClient.sendHello.
