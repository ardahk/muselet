# architect digest - pass 84 (2026-10-25T08:32Z)
Reviewed: main 73b8031, a Swift-only change: Observe now tolerates duplicate refs. `Dictionary(uniqueKeysWithValues:)` trapped and crashed the app; it now keeps the first record. wip/local 51d833a is the same tree as main. agentic-fixes2 104a411 only merges main.
Tests (Linux): agentic-fixes2, including test_agentic_fixes2: 186 passed. The Swift was reviewed by reading only.
Open: P0 0, P1 16, P2 10. No new findings. Re-checked architect-48 (still open). The 51/49 code is unchanged since 3e323a9.

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

Watch (not filed): 73b8031 stops the crash, but duplicate refs mean two live elements map to the same ref. With first-wins, `press #N` on the second element acts on the first. Find where duplicates come from (the sibling-label / ref session code, see architect-52), or log them in the trace. Also still open: agentic-fixes2 drops an invalid expect and runs the action without it.

## Next moves (max 5)
1. architect-51: run the live app cases on LoRA + agentic-fixes2 vs the 35B (pass count and step p50), and keep the winner. The 35B fails the 3 s gate offline.
2. architect-48: fix the timer-control match; 'set a timer for 10 minutes to stop the oven' still cancels, now on the 35B.
3. architect-45: re-score the LoRA holdout without the near-paraphrase items, or caveat .850 in devpost/REPORT before submission.
4. architect-42: restore the screenshot start-state, then run HobbyLM r4 with ROUTER=it2 MEMORY=0 LONGTERM=0 and AGENTIC_APPS/BLIND_PLANNER/PLANNER pinned; report passes/125 with skips and timeouts counted as failures (32/37/40/44).
5. architect-49: decide AGENTIC_APPS from on-vs-off timer/event slice numbers.
