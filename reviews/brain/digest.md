# brain digest — pass 9 (2026-10-24T07:55:00Z)

Heads: main 4a74659 (merged PR #10 cloud/brain-2, #9 grounding, #7 finance-2, #5 advisor-2, #6 pitch), wip/local 85c73ed (ml/ == main), cloud/bench c3ca0b3, cloud/data-pipeline 9c526b1.
All 17 product suites pass on main (test_decision.py real-model test skipped: Linux CPU). Runtime route render vs data-pipeline v2 samples: 50/50 token-identical.

Resolved this pass (on main via PR #10): brain-9 (P0), brain-3, -4, -6, -10, -11, -13.

## Open P0/P1 (ranked)
1. brain-15 (P1) Route parity gate disabled on main: stale v1 samples xfail — ml/tests/test_route_parity.py

## Open P2
- brain-14 Confirm token survives harmless actions until next dangerous one — ml/src/brain/orchestrator.py:630
- brain-8 Runtime last_action quoting differs from training — ml/src/brain/orchestrator.py:310
- brain-12 Pending ASK captures unrelated next utterances — ml/src/brain/orchestrator.py:172

## Highest-leverage next moves
1. Copy v2 route_render_samples.jsonl from cloud/data-pipeline to main and make catalog mismatch a hard failure (brain-15).
2. Bind planner `confirm` to the immediately following action; clear on any executed action (brain-14).
3. Quote all string args in last_action like training (brain-8) — one-line change, removes a train/runtime context mismatch.
4. Gate pending-ASK capture on System 1 routing the reply to ANSWER/none rather than a 90 s window (brain-12).
5. Verify hybrid DeltaNet cache-snapshot exactness on the M5 (not verifiable on Linux CPU).
