# brain digest — pass 15 (2026-10-24T09:10:00Z)

Heads: main bb494af (merged PR #11 brain-3, #12 finance-3, #13 advisor-3; + evals/router_check.py), wip/local c85a000 (ml/ == main), cloud/bench f584cb2, cloud/data-pipeline 70b7d1b (no lane changes).
Main: all 19 product suites pass (test_decision.py real-model test skipped: Linux CPU). Runtime route render = parity_300 300/300 tokens (pass 14).

## Open P0/P1 (ranked, all on main)
1. brain-16 abs_level turns relative volume requests into near-zero absolute levels — ml/src/brain/orchestrator.py:65
2. brain-17 Compound check adds serial route passes before every 'and' utterance — ml/src/brain/orchestrator.py:336
3. brain-15 Route parity gate disabled on main: stale v1 samples xfail — ml/tests/test_route_parity.py

## Open P2
- brain-19 no_text_target hint not used by the planner or the reply (web_ax_pending/script exit fixed) — orchestrator.py, replies.py
- brain-18 BatchCutter skips bare mute/wifi/bluetooth lines; batches exceed 5 actions — planner.py:50
- brain-14 Confirm token survives harmless actions — orchestrator.py:822
- brain-8 last_action quoting: training always quotes query/duration — orchestrator.py:424
- brain-12 Pending ASK captures unrelated utterances — orchestrator.py:271

## Highest-leverage next moves
1. Anchor abs_level to the clause end; reject number ranges ('two to three') and times ('at 3 pm') (brain-16). This is now on main and in the demo path.
2. Route the whole utterance first and reuse the speculative hit; call _compound only on MULTI_STEP or p_top < tau (brain-17).
3. Land parity_300.jsonl on main and point test_route_parity at it; make a catalog mismatch a hard fail (brain-15).
4. Pass catalog.skills into BatchCutter (brain-18); bind confirm to the next action (brain-14).
5. Map no_text_target to 'Click a text field first' and feed the `observed` hint to the planner (brain-19).
