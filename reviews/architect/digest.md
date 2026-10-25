# architect digest - pass 57 (2026-10-25T00:52Z)
Reviewed: main eb3e945 (design brief only), wip/local 3f21dc6, new design b93bb50, docs-demo-3 c615c37, memory-llm-gate 6864386, panel-hook-fix ef35421. No new findings. design removes the Shortcuts timer backend + SettingsView by explicit user request (brief §3) and keeps Settings › Memory in PanelView; Muselet timer fallback kept. docs-demo-3 discloses greedy t512 (.763, 1.7 s) next to qwen and the live-suite 27/43-ran skip, quotes T1/T2 separately (good), but still cites it3 overlap 0 only as "(lane brief)" (architect-37). memory-llm-gate: lexical guard on LLM rewrites, 40/40 memory tests pass on Linux, no re-measured resolution/false-rewrite yet; MEMORY_LLM stays 0. Re-checked open findings: none changed (serve_brain.sh@eb3e945:49-50 still THINK_SAMPLER qwen, VERIFY_DONE on; replay.py still unpinned).

## Open P1 (ranked)
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
5. Run a live rehearsal of the 3:00 script with think + verify on and record per-beat latency. The planner beats now cost ~2-3 s per step.
