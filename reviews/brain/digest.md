# brain digest — pass 12 (2026-10-24T08:25:00Z)

Heads: main 76a03c1 / wip/local 34ddf5f (no ml/ changes since pass 9: planner prompt + Swift only), cloud/brain-3 14a3f52, cloud/advisor-3 ca93147, cloud/finance-3 31be399, cloud/bench 6e7cd09 (merge of main only), cloud/data-pipeline 0f3df7f (parity_300 export).
All product suites pass on brain-3, advisor-3 and finance-3 (test_decision.py real-model test skipped: Linux CPU).

Pass 12: main 280715d / wip/local 38768f3 changed AGENTS.md (new HandsKit result fields, live-test safety) and Swift only; data-pipeline 1d65818 is training eval only. No ml/ changes. New: brain-19. Standing decision 'reviewed PRs that pass tests may be merged' applies to cloud/brain-3: its suites pass, but none of its tests cover brain-16/17/18.

## Open P0/P1 (ranked)
1. brain-16 (P1, brain-3) abs_level turns relative volume requests into near-zero absolute levels — ml/src/brain/orchestrator.py:65
2. brain-17 (P1, brain-3) Compound check adds serial route passes before every 'and' utterance — ml/src/brain/orchestrator.py:336
3. brain-19 (P1, main) Brain on main ignores new HandsKit fields: web_ax_pending, script exit, no_text_target — ml/src/brain/orchestrator.py
4. brain-15 (P1, main) Route parity gate disabled on main: stale v1 samples xfail — ml/tests/test_route_parity.py

## Open P2
- brain-18 BatchCutter skips bare mute/wifi/bluetooth lines; batches exceed 5 actions (brain-3) — ml/src/brain/planner.py:50
- brain-14 Confirm token survives harmless actions — orchestrator.py
- brain-8 last_action quoting differs from training — orchestrator.py
- brain-12 Pending ASK captures unrelated utterances — orchestrator.py

## Highest-leverage next moves
1. Fix brain-16, then merge cloud/brain-3: that also closes most of brain-19 (web_ax_pending, script exit/stderr). Anchor abs_level to the clause end and reject number ranges and times (brain-16).
2. Reorder: whole-utterance route and speculative hit first; call _compound only on MULTI_STEP or low confidence (brain-17).
3. Copy v2 route_render_samples.jsonl to main; make a catalog mismatch a hard fail (brain-15).
4. Pass catalog.skills into BatchCutter (brain-18); bind confirm to the next action (brain-14).
5. Verify hybrid DeltaNet cache-snapshot exactness on the M5 (could not be verified on this Linux CPU).
