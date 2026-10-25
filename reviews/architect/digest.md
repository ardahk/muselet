# architect digest - pass 59 (2026-10-25T01:24Z)
Reviewed: main 9be963d (memory #71/#72 merged, docs-demo-3 #68, proxy stale-client displace 517e056), wip/local 4d22445. architect-38 resolved (main holdout .617/.0195, tune .97/0). New: architect-39 (P1): the proxy displacement branch is unreachable (the lock is held across _forward_pair), so a stale client still wedges cases, and their harness_timeouts drop out of the replay n (architect-32). claims.md still quotes memory .574; the holdout is now .617. Other open findings unchanged.

## Open P1 (ranked)
0. architect-39 - Proxy stale-client displacement unreachable; wedged cases shrink replay n - bench/harness/proxy.py
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
1. HobbyLM r4 with ROUTER=it2 explicitly (it3 is now default; architect-37) on the Mac, no --exclude-kind, passes/125 with skips as fails. This is the only competitor claim within reach. ~1.5 h.
2. Flip THINK=512 with the greedy sampler, not qwen (same pass rate, -0.85 s/step, deterministic for the stage). 1 line.
3. Fit VERIFY_P now that verify is on by default. Label v2-tune final states plus live_t1 traces and target false reject <= 5%, else VERIFY_DONE=off for the demo. ~30 min.
4. Mac decisions run (muselet-decisions-4b-mlx4, T=1) on JevBench + TD through the shim. Quote only against the SE. ~30 min.
5. Fix the proxy lock scope (architect-39) before the HobbyLM r4 run. Run reviews/architect/tests/repro_proxy_displace.py, which must pair client B. Then rehearse the 3:00 script with think + verify + memory on.
