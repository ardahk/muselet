# hands — digest (pass 44)

Pass 44: main 2a2c2a9 and wip/local 4f963a7 have no app/ changes since pass 43, so hands-26 and hands-27 are re-verified as still open (orchestrator.py:1896 and BrainClient.swift:91 are unchanged). cloud/w9-safety 50a3b25 only touches a test. cloud/memory 4b519b1 adds ctx.url and ctx.window_title to UtteranceCtx: bounded BFS of up to 80 nodes within a 0.15 s budget, AX only, captured asynchronously at key-down. No issues found there. cloud/memory-eval has no app/ changes.

Pass 43 reviewed main 3772f7c. That covers the clock-timers merge (ClockTimers.swift, the Shortcuts CLI backend with a 10 s kill, and the timer_backend RPC, plus the timers_cancel unsupported/failed split) and the mascot redesign. Also reviewed wip/local 8fcf55f and the cloud heads per state.json. Static analysis only; Linux VM.

Open: 0 P0, 1 P1, 5 P2.

Open P0/P1, ranked:
- P1 hands-26: brain strips `expect` from act and runs a single-shot verify, so HandsKit's 1.5 s expect polling never runs (ml/src/brain/orchestrator.py:1896,2034; app/Sources/HandsKit/RPC.swift:173)

Open P2: hands-27 (headless hello frames are bottom-left, BrainClient.swift:86), hands-25, hands-20, hands-16, hands-10.

Highest-leverage next moves:
1. hands-26: send expect inside act. This is one line in the orchestrator, and slow-UI expects stop failing. It also saves one RPC plus one AX walk per action.
2. hands-27: share ScreenGeometry.cgBounds with BrainClient so headless and bench runs on multi-display rigs get correct grounder zoom scale.
3. Not filed (needs a live check): timers_cancel runs the generic `Muselet Cancel Timer` shortcut once per Clock timer id (Skills.swift:394-400). If that shortcut cancels all or the wrong Clock timer, the per-id `cancelled` report is wrong.
4. Not filed: start_timer can block the serial RPC queue for up to ~24 s cold (shortcuts list plus run, 10 s each plus kill). That is under the 45 s skill timeout, but any queued observe/act waits.
