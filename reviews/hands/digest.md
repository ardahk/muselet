# hands — digest (Pass 67)

Open: 0 P0, 3 P1, 9 P2.

Ranked open P0/P1:
1. P1 hands-34 (main dc6f2f5, Launch.swift:224-232): fix-same-tab merged unchanged. Same-tab open_url/web_search posts cmd+L, waits a fixed 80 ms, then types the URL plus Return without checking the address bar has focus. The brain uses it by default whenever a browser is frontmost.
2. P1 hands-29 (main, ClockAX.swift): Clock start and cancel bring Clock to the front and never switch back, and there's no opt-out.
3. P1 hands-26 (main, orchestrator.py:3051): the brain removes `expect` from `act`, so the app's built-in polling never runs.

Next moves (max 5):
1. hands-34: poll for the address-bar focus (2 stable samples, <= 0.5 s) before typing; otherwise fall back to a new tab.
2. hands-29: record the frontmost pid before openApp and re-activate it after Start/Cancel.
3. hands-26: send `expect` with `act` and drop the extra verify when expect_ok is present.
4. hands-35: wait for the Go-to-folder sheet before typing in the Premiere import, and fail when OCR finds no footage name.
5. hands-33: when ax.pressed, call clockAXRead() once before starting the Muselet fallback.

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
