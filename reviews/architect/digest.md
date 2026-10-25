# architect digest - pass 82 (2026-10-25T07:55Z)
Reviewed: main 5d135d0 (adds only the agentic-fixes2 brief, which merges without review by the user's call). wip/local c86fec4 sets _force_blind in _agentic_route and the timer-control route, so app tasks plan on the 35B. docs-final bf9118d updates REPORT, pitch, claims and AGENTS. Its competitor claims are honest: no valid HobbyLM score, and DeskMind leads on decisions. It still quotes the LoRA's .850 without a caveat.
Tests (Linux): wip agentic/evidence/loop/fallback/same-tab: 138 passed. Main code is unchanged since cf33215 (347 passed last pass).
Open: P0 0, P1 16, P2 10. No new IDs. architect-51 is now backed by recorded numbers, and wip makes it worse.

## Open P0/P1 (ranked)
- architect-51 [P1] 35B blind planner is 5.95 s p50 (FAIL > 3 s), .807 < LoRA .850 on our bench; wip forces it on all agentic-app + timer tasks
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

Watch (not filed): the agentic-fixes2 brief merges without review by the user's call. I'll review it after the merge. REPORT.md:184@bf9118d still labels the base-4B k=1 row "shipped 4B" although the LoRA serves.

## Next moves (max 5)
1. architect-51: don't merge the wip _force_blind lines until a live LoRA-vs-35B run on app tasks exists. The 35B fails the 3 s gate on our own bench (5954 ms) and scores lower (.807 vs .850). Keep BLIND_PLANNER explicit.
2. architect-48: add the timer-control match to agentic-fixes2; 'set a timer for 10 minutes to stop the oven' must start a timer.
3. architect-45: re-score the LoRA holdout without the near-paraphrase items, or caveat .850 in devpost/REPORT before submission.
4. architect-42: restore the screenshot start-state, then run HobbyLM r4 with ROUTER=it2 MEMORY=0 LONGTERM=0 and AGENTIC_APPS/BLIND_PLANNER pinned; report passes/125 with skips and timeouts counted as failures (32/37/40/44).
5. architect-49: decide AGENTIC_APPS from on-vs-off timer/event slice numbers, not by default.
