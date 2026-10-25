# architect digest - pass 80 (2026-10-25T07:05Z)
Reviewed: main 3a0860c (untracks the models/ml/.venv symlinks -> architect-50 resolved; adds BLIND_PLANNER=escalate and makes it the implicit default when the 35B is cached), wip/local 83cf584 (same tree as main), agentic-evidence 1918cad (goal-derived timer_start/play auto-done; label fields are not counted as countdowns), app-knowhow c69dfec (Clock label / Reminders hints) and browser-flow 485763f (web UI guard rejects hand-built same-site search URLs and address-bar queries).
Tests (Linux): main 257 passed (a fresh worktree runs uv with no workaround); agentic-evidence 103; browser-flow 51; app-knowhow 26.
Open: P0 0, P1 16, P2 9. New: architect-51. Resolved: architect-50. 48 and 49 re-checked: still open on 3a0860c.

## Open P0/P1 (ranked)
- architect-51 [P1] (new) BLIND_PLANNER defaults to 35B-A3B + THINK 512 whenever its HF cache exists: unmeasured, ~5-7 s/step vs 3 s gate, +19 GB
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

Watch (not filed): browser-flow's web UI guard fails `url` to a same-host search URL. Check that a legitimate site-search deep link the user dictated still works, since the guard only checks the host.

## Next moves (max 5)
1. architect-51: pin BLIND_PLANNER to an explicit default (no cache probe), and measure escalate vs base vs LoRA on blind/agentic slices before shipping 35B there.
2. architect-48/49: fix the timer-control match, and default AGENTIC_APPS=0 or measure on vs off; pin AGENTIC_APPS and BLIND_PLANNER in r4 run configs.
3. architect-42: restore the screenshot start-state, then smoke-test one calc, one screenshot and one none case on the Mac.
4. Run HobbyLM r4 with ROUTER=it2 MEMORY=0 LONGTERM=0 and the knobs pinned, and report passes/125 with skips and timeouts counted as failures (architect-32/37/40/44).
5. architect-45: re-score the planner holdout with the near-paraphrase items removed.
