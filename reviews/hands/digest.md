# hands — digest (Pass 58)

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
