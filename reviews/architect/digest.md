# architect digest - pass 66 (2026-10-25T03:28Z)
Reviewed: main fa0f040 (design #70: Settings panel, Clock-only timers, clock hint removed; 7235a34: per-start memory DB for benchmark brains), wip/local 973a9b0 (snapshot on the pre-#70 base), design-polish bf4ae64 (Swift UI only, static review), and memory-writes d04e26c (person writes only from explicit my-X-is / X-is-my / call-me; episodes only for >=2 steps in a real app; 165 tests pass; holdout .617/.0195 unchanged). New: architect-44 (P1): working memory is not isolated per benchmark run or case. architect-42/43 still open (bench/hobbylm unchanged). Open: P0 0, P1 14, P2 8.

## Open P1 (ranked)
00000. architect-44 - Working memory not isolated across benchmark cases - ml/src/brain/orchestrator.py
0000. architect-43 - Calc checker patch breaks provenance; replay cannot start - bench/hobbylm/upstream/hobby/calc_checker.swift
000. architect-42 - 13d0486 drops start-state screenshot capture; 20/125 r4 cases crash - bench/hobbylm/replay.py
00. architect-40 - Sealed r4 failures patched post-hoc; rerun = tuned-on-test - ml/src/brain/orchestrator.py
1. architect-37 - it3 default router; no it3 sealed overlap check; replay unpinned - tools/serve_brain.sh
1b. architect-29 - No winning competitor number (TD tie within 1 SE, JevBench loses, HobbyLM r4 missing) - pitch/claims.md
2. architect-33 - Done verifier default on with unfitted 0.5 threshold (on main) - ml/src/brain/orchestrator.py
3. architect-36 - Think shipped with sampled qwen (on main), +853 ms/step for 1 net item - cloud/handoff/notes/planner_think_eval.md
4. architect-32 - HobbyLM replay drops skips from denominator vs /125 claim - bench/hobbylm/replay.py
5. architect-28 - Holdout paraphrases in bank/demos; think/lora gates include them - ml/src/brain/plan_bank.py
6. architect-27 - premiere_command doesn't verify; partial fix unmerged (Premiere out of demo) - app/Sources/HandsKit/Skills.swift
7. architect-26 - Planner prompt teaches cmd+t as Premiere transition - prompts/planner_system.md
8. architect-13 - System One tinker backend reports as 'muselet' - bench/systemone/cli.py
9. architect-8 - No Mac parity result for it2 - evals/router_check.py
(P2: 35, 34, 31, 30, 20, 15, 16)

## Highest-leverage next moves
1. HobbyLM r4: quote run 20261025T004223Z (first run; check that it used ROUTER=it2) as passes/125, with skips and harness_timeouts counted as fails. Do not quote a rerun made after the D04-D06 patch as the result (architect-40).
2. Flip THINK=512 with the greedy sampler, not qwen (same pass rate, -0.85 s/step, deterministic for the stage). 1 line.
3. Fit VERIFY_P now that verify is on by default. Label v2-tune final states plus live_t1 traces and target false reject <= 5%, else VERIFY_DONE=off for the demo. ~30 min.
4. Mac decisions run (muselet-decisions-4b-mlx4, T=1) on JevBench + TD through the shim. Quote only against the SE. ~30 min.
5. Rehearse the 3:00 script with think + verify + memory on (proxy slot recovery landed in 69a9650; architect-39 resolved).
