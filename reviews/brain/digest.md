# brain digest — pass 18 (2026-10-24T09:50:00Z)

main 28dc259 changes only evals/: the planner bench holdout set and the ARGS end-to-end score in router_check. No findings there. wip/local e1701a3 has the same tree as main. Every pass-16 repro still fails on main.
cloud/brain-4 3aca368 (separate ARGS model, planner flags, OpConstraint, brain-16 attempt): 907 passed, 2 skipped, 51 xfailed. The ARGS-model split shares weights when the paths are equal. OpConstraint allows stop tokens at line start, so decoding can still end a batch. Of the pass-16 repros, brain-16 still fails, and so do the other 5 (brain-17/18/14/12/8).
cloud/hobby-gaps 14ff59b (calculator execution, relative controls): 1 failed, 847 passed. It brings the new P0 brain-20.
MERGE NOTE: brain-4 and hobby-gaps conflict in orchestrator.py, because both rewrite the volume/brightness handling in _run_skill with different delta scales (brain-4 rel_delta: notch = 10; hobby-gaps: normalize_delta, brightness +-15). The lead must pick one scheme.

## Open P0/P1 (ranked)
1. brain-20 (P0, cloud/hobby-gaps) calc.result runs before the router and hijacks commands containing numbers — orchestrator.py:296, calc.py:_problem_expression
2. brain-16 (P1, main; partly fixed on cloud/brain-4, with a new 'up 20%' -> absolute 20 regression) abs_level misreads relative requests — orchestrator.py abs_level
3. brain-21 (P1, cloud/hobby-gaps) set_brightness delta always fails in HandsKit — Skills.swift:361
4. brain-17 (P1, main) compound check adds serial route passes before every 'and' utterance — orchestrator.py:336
5. brain-15 (P1, main) route parity gate disabled on main: stale v1 samples xfail — ml/tests/test_route_parity.py:60-91

## Open P2
brain-14 (confirm token carry-over), brain-18 (BatchCutter bare skills), brain-12 (pending ASK capture), brain-19 (no_text_target), brain-8 (last_action quoting). Repros for all of these are in reviews/brain/tests/test_brain_pass16.py.

## Highest-leverage next moves
1. Do not merge cloud/hobby-gaps until calc is gated behind the ANSWER route (brain-20). Its own suite is also red.
2. brain-16 on brain-4: treat 'up/down ... N%' as relative and reject 'at N pm'. Repros are in test_brain_pass18.py and test_brain_pass16.py.
3. Pick one relative-delta scheme (brain-4 rel_delta) before merging brain-4 and hobby-gaps, and drop the other.
4. brain-21: apply brightness delta in Swift from brightnessGet, or don't emit delta at all.
5. brain-15: land parity_300.jsonl on main and point test_route_parity at it.
