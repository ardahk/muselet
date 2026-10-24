# brain digest — pass 16 (2026-10-24T09:25:00Z) — full re-verification against main 2920225

Main 2920225: all 20 product suites pass (incl. new test_split_model 2/2). Fresh repros for every open finding are in reviews/brain/tests/test_brain_pass16.py; all 6 tests fail on 2920225.
Branch-only findings: none left. Every open item reproduces on main. Findings from cloud/* branches that are now merged were resolved in passes 9 and 15. The 2 failures in test_brain_pass4.py are stale tests (brain-13 is fixed), so ignore them.
New merges reviewed: split_model (5bc295d) is correct for mlx-lm qwen3_5. Model.model maps to language_model.model, the untied head is taken from language_model.lm_head, and 4B falls back to the tied embedding. generic_decide (bench #8) assigns IDS = usable_ids, so the brain-5 class of bug is not present. planner_offline grading uses dsl.action_line(ln, skills) like the runtime, but its BatchCutter() has the same blind spot as brain-18.

## Open P0/P1 (ranked)
1. brain-16 abs_level turns relative volume requests into near-zero absolute levels — ml/src/brain/orchestrator.py:65-80
2. brain-17 Compound check adds serial route passes before every 'and' utterance — ml/src/brain/orchestrator.py:336
3. brain-15 Route parity gate disabled on main: stale v1 samples xfail — ml/tests/test_route_parity.py:60-91

## Open P2
- brain-14 Confirm token survives a harmless action (Send runs on 'Open settings?' confirm) — orchestrator.py:822
- brain-18 BatchCutter skips bare mute/wifi/bluetooth lines — planner.py:50 (+ evals/planner_offline.py:393)
- brain-12 Pending ASK captures unrelated utterances — orchestrator.py:269
- brain-19 no_text_target hint unused — orchestrator.py / replies.py
- brain-8 last_action quoting vs training — orchestrator.py:424

## Highest-leverage next moves
1. brain-16: anchor abs_level to the clause end and reject 'N to M' ranges and am/pm times. One function; the repro test is ready.
2. brain-17: route the whole utterance first and reuse the speculative hit; call _compound only on MULTI_STEP or p_top < tau.
3. brain-15: land parity_300.jsonl on main and point test_route_parity at it. The runtime already matches 300/300.
4. brain-14: clear _batch_confirmed after any executed action (one line in _exec_one).
5. brain-18: BatchCutter(skills=catalog.skills) in both the planner and evals/planner_offline.py.
