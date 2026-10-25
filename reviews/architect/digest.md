# architect digest - pass 85 (2026-10-25T08:50Z)
Reviewed: main b7b38f9, which merges agentic-fixes2 b9cd089 and docs-final bf9118d (both reviewed in passes 82-84). It adds ab850b3: blind/agentic tasks get 30 turns / 300 s, planner expects are soft, and the loop guard trips at 5. It adds b7b38f9: PLANNER=35b observes 350 AX nodes (MUSELET_OBS_NODES). wip/local e03e2c8 is the same tree as main.
Tests (Linux): main agentic/fixes2/evidence/finish/loop/fallback/same-tab/app-hints/planner-loop: 211 passed, 1 skipped.
Open: P0 0, P1 17, P2 10. New: architect-53. architect-48 re-checked: still open.

## Open P0/P1 (ranked)
- architect-51 [P1] Main now plans every agentic-app + timer task on the 35B (5.95 s p50 on our bench, > 3 s gate; .807 < LoRA .850); switch based on qualitative live failures
- architect-53 [P1] (new) Soft expects on blind/agentic tasks skip the loop guard; repeated failing actions run up to 30 turns / 300 s
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

Watch (not filed): MUSELET_OBS_NODES=350 more than doubles observation tokens for PLANNER=35b. That's opt-in, but each step gets longer prefill on top of the 35B's ~6 s. Invalid expects are still dropped (agentic-fixes2, now on main).

## Next moves (max 5)
1. architect-53: on blind tasks, still stop on the same fail_key twice in a row, even when the expect is soft. Add the repeated-press test.
2. architect-51: run the live app cases on the LoRA vs the 35B (pass count and step p50), and keep the winner. The 35B fails the 3 s gate offline.
3. architect-48: fix the timer-control match; 'set a timer for 10 minutes to stop the oven' still cancels.
4. architect-45: re-score the LoRA holdout without the near-paraphrase items, or caveat .850 in devpost/REPORT (now on main) before submission.
5. architect-42: restore the screenshot start-state, then run HobbyLM r4 with ROUTER=it2 MEMORY=0 LONGTERM=0 and AGENTIC_APPS/BLIND_PLANNER/PLANNER pinned; report passes/125 with skips and timeouts counted as failures.
