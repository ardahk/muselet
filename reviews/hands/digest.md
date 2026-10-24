# hands — digest (pass 47)

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

Open: 0 P0, 3 P1, 6 P2.

Open P0/P1, ranked:
- P1 hands-28: an unverified Clock AX start is reported as a set timer that never fires (cloud/hands-clock app/Sources/HandsKit/ClockAX.swift, Skills.swift:925)
- P1 hands-29: Clock AX start and cancel steal focus and never restore the prior app (cloud/hands-clock app/Sources/HandsKit/ClockAX.swift:316,421)
- P1 hands-26: the brain strips `expect` from act, so HandsKit's expect polling never runs (ml/src/brain/orchestrator.py:1896; app/Sources/HandsKit/RPC.swift:173)

Open P2: hands-30 (Clock wheel stepping latency), hands-27, hands-25, hands-20, hands-16, hands-10.

Highest-leverage next moves:
1. hands-28 before merging hands-clock: an unverified start must fall back, or keep a real Muselet alarm. Otherwise users get silent missed timers.
2. hands-29: save and restore the frontmost app around the Clock AX calls, so compound utterances and the demo keep focus.
3. hands-26: pass expect inside act. That is a one-line change, fixes slow-UI expect failures, and saves one RPC plus one AX walk per action.
4. hands-30: cap clockAXStart at about 5 s and step wheels in the shorter direction.
5. hands-27: use CGDisplayBounds in BrainClient.sendHello.
