# architect digest - pass 78 (2026-10-25T06:30Z)
Reviewed: agentic-apps 1904638 (merges main e2f7e5e; the timer_control skill is removed and timer controls go back to the planner with the Clock hint). Main e2f7e5e and wip/local 3f8e2f8 are unchanged. Tests: agentic-apps 147 passed. Re-checked architect-48 on 1904638: 'set a timer for 10 minutes to stop the oven' -> cancel, so it is still open. Re-checked architect-49: --agentic-apps still defaults to on (cli.py:413, serve_brain.sh:79@1904638), so it is still open. No new findings.
Open: P0 0, P1 15, P2 9.

## Open P0/P1 (ranked)
- architect-45 [P1] Shipped LoRA planner's holdout .850 rests on a decontam gate that misses word-order paraphrases of holdout goals
- architect-44 [P1] Benchmark memory isolation misses working memory: cross-case rewrites in sealed runs, shared working.json
- architect-42 [P1] 13d0486 drops start-state screenshot capture: 20/125 r4 cases (screenshot+none) crash at final snapshot
- architect-40 [P1] Sealed HobbyLM r4 failures patched post-hoc; any r4 rerun is tuned-on-test
- architect-37 [P1] it3 now default router; sealed-set overlap check not recorded for it3
- architect-33 [P1] Done verifier ships on by default with an unfitted 0.5 threshold
- architect-32 [P1] HobbyLM replay drops skips from denominator; claim template says /125
- architect-29 [P1] No competitor benchmark number exists with 11 h left
- architect-28 [P1] Retrieval bank holds paraphrases of v2-holdout goals; ship gate inflated
- architect-27 [P1] premiere_command sends shortcuts without Timeline focus, always reports success
- architect-26 [P1] Planner prompt teaches cmd+t as Premiere default transition (Mac: cmd+d)
- architect-13 [P1] Cloud Tinker System One backend reports as 'muselet', untagged
- architect-8 [P1] Phase-1 LoRA likely misses Sat 12:00 PDT; no fallback router measured

## Next moves (max 5)
1. architect-45: re-score the LoRA vs the base planner on holdouts with the J>=.5 near-paraphrase items removed, and quote that number next to .850.
2. architect-42: restore the screenshot start-state, then smoke-test one calc, one screenshot and one none case on the Mac.
3. Run HobbyLM r4 with ROUTER=it2 MEMORY=0 LONGTERM=0 (architect-37/44), name the patched calc checker, and report passes/125 with skips, timeouts and ungradable cases counted as failures (architect-32/40).
4. Fit VERIFY_P on the LoRA planner's traces, or turn VERIFY_DONE off for the demo (architect-33).

5. Before the demo, smoke-test evals/live_premiere.jsonl on the Mac (Window > Timeline, Sequence > Apply Video Transition) and change cmd+t to the real shortcut in planner_system.md:46 (architect-26/35).








