# architect digest - pass 83 (2026-10-25T08:20Z)
Reviewed: main 3e323a9 (cef8797: agentic-app and timer-control tasks force the 35B blind planner; #101 Spotify play with an accent-insensitive gate, a gated title double-click and AppleScript player-state evidence; PLANNER=35b option). wip/local b8eeec4 is the same tree as main. agentic-fixes2 b9cd089 makes the hint state the exact text, guards asks for text already given, drops invalid expects, adds YouTube watch-url play evidence and the bare-site-title loading check.
Tests (Linux): main agentic/evidence/finish/loop/fallback/same-tab/app-hints/planner-loop 206 passed; agentic-fixes2 206 passed on the same files (its new test_agentic_fixes2.py is not in that set). Spotify Swift/AppleScript paths were reviewed by reading only.
Open: P0 0, P1 16, P2 10. No new IDs. architect-51 is now on main; architect-48 is still present on main and agentic-fixes2.

## Open P0/P1 (ranked)
- architect-51 [P1] Main now plans every agentic-app + timer task on the 35B (5.95 s p50 on our bench, > 3 s gate; .807 < LoRA .850); switch based on qualitative live failures
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

Watch (not filed): agentic-fixes2 _drop_invalid_expect runs the action without its expect when the predicate doesn't parse. For consequential actions this goes against 'every consequential action carries an expect'. Send/buy still have the confirm gate, but verification for that step is lost. Consider rejecting the line (no strike) instead of dropping only the expect for risky actions.

## Next moves (max 5)
1. architect-51: run the live app cases on LoRA + agentic-fixes2 vs the 35B (pass count and step p50), and keep the winner. The 35B fails the 3 s gate offline.
2. architect-48: fix the timer-control match; 'set a timer for 10 minutes to stop the oven' still cancels, now on the 35B.
3. architect-45: re-score the LoRA holdout without the near-paraphrase items, or caveat .850 in devpost/REPORT before submission.
4. architect-42: restore the screenshot start-state, then run HobbyLM r4 with ROUTER=it2 MEMORY=0 LONGTERM=0 and AGENTIC_APPS/BLIND_PLANNER/PLANNER pinned; report passes/125 with skips and timeouts counted as failures (32/37/40/44).
5. architect-49: decide AGENTIC_APPS from on-vs-off timer/event slice numbers.
