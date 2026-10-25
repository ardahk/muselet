# architect digest - pass 79 (2026-10-25T06:50Z)
Reviewed: main de1070d (merges agentic-apps #91 plus autodone f30bf1d/967626e: programmatic timer/cart finish evidence, progress_evidence rename), wip/local 52e4b94 (main minus the ml/.venv symlink), and new branches agentic-evidence c4703c4 (one evidence() for done + auto-done, app kinds auto-finish), app-knowhow fc92f6b (app planner tips; hints never redirect routing) and browser-flow c0421e6 (default-browser rewrite from the LaunchServices plist, same tab, compound fallback through a deferred server for safe skills).
Tests (Linux, UV_PROJECT_ENVIRONMENT outside the tree): main agentic/catalog/planner/fallback 147 passed; agentic-evidence 63 passed; app-knowhow test_app_hints 25 passed; browser-flow 49 passed. test_planner_think needs libmlx, so it can't run on Linux.
Open: P0 0, P1 16, P2 9. New: architect-50. architect-48 and architect-49 are now both on main.

## Open P0/P1 (ranked)
- architect-50 [P1] (new) main commits absolute symlinks models and ml/.venv -> /Users/arda/cal13.0/...; `uv run` fails on any clean clone
- architect-48 [P1] Timer-control pre-route hijacks 'set a timer ... to stop the oven' into a cancel (main de1070d)
- architect-49 [P1] agentic-apps on by default on main: start_timer/create_event and 10 more go through the planner, unmeasured (38/125 r4)
- architect-45 [P1] Shipped LoRA planner's holdout .850 rests on a decontam gate that misses word-order paraphrases of holdout goals
- architect-44 [P1] Benchmark memory isolation misses working memory: cross-case rewrites in sealed runs, shared working.json
- architect-42 [P1] 13d0486 drops start-state screenshot capture: 20/125 r4 cases (screenshot+none) crash at final snapshot
- architect-40 [P1] Sealed HobbyLM r4 failures patched post-hoc; any r4 rerun is tuned-on-test
- architect-37 [P1] it3 now default router; sealed-set overlap check not recorded for it3
- architect-33 [P1] Done verifier ships on by default with an unfitted 0.5 threshold
- architect-32 [P1] HobbyLM replay drops skips from denominator; claim template says /125
- architect-29 [P1] No competitor benchmark number exists
- architect-28 [P1] Retrieval bank holds paraphrases of v2-holdout goals; ship gate inflated
- architect-27 [P1] premiere_command sends shortcuts without Timeline focus, always reports success
- architect-26 [P1] Planner prompt teaches cmd+t as Premiere default transition (Mac: cmd+d)
- architect-13 [P1] Cloud Tinker System One backend reports as 'muselet', untagged
- architect-8 [P1] Phase-1 LoRA likely misses Sat 12:00 PDT; no fallback router measured

Watch (not filed): agentic-evidence auto-finishes app kinds from observation evidence (keyword match on composer/countdown text). Confirm it never auto-dones a send/compose before the confirm gate. browser-flow rewrites an unrequested browser to the default browser: check that "open X in Chrome" still counts as requested.

## Next moves (max 5)
1. architect-50: untrack the models and ml/.venv symlinks and fix .gitignore before any submission or judge clone.
2. architect-48/49: fix the timer-control match, and default AGENTIC_APPS=0 or measure on vs off on the timer/event slices; pin it in run configs.
3. architect-42: restore the screenshot start-state, then smoke-test one calc, one screenshot and one none case on the Mac.
4. Run HobbyLM r4 with ROUTER=it2 MEMORY=0 LONGTERM=0 AGENTIC_APPS pinned, and report passes/125 with skips and timeouts counted as failures (architect-32/37/40/44).
5. architect-45: re-score the planner holdout with the near-paraphrase items removed.
