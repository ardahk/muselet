# brain digest — pass 19 (2026-10-24T10:05:00Z)

main 758a017 has no ml/ changes since 2920225. It changes the live runner, pitch, one planner_offline holdout accept regex and the cloud/builder_brain5.md brief. wip/local a3f82f1 has the same tree as main. Every pass-16 repro still fails on main.
cloud/hobby-gaps 929b931: 855 passed, 2 skipped, 51 xfailed (green again). brain-20 (P0) is RESOLVED: calc now runs before the router only when the app is Calculator or the user says 'calculator' (orchestrator.py:299-305). New P1 brain-23: '…all the way up' is overwritten with +25.
cloud/brain-4 dfb66a3 (history default dsl, opt-in --planner-escalate-model): 914 passed, 2 skipped, 51 xfailed. New P1 brain-22: the few-shot prefix teaches the '[ok] x' format, but Last batch now sends 'x -> ok', which still parses as an executable action. The escalation loop-guard logic itself is fine: it resets the streak once and stops after two more failures.
MERGE NOTE: there are now THREE relative-volume/brightness schemes: brain-4 rel_delta (notch = 10), hobby-gaps (normalize_delta 'way' = 25, brightness ±15), and the brain-5 brief (10/30, HandsKit delta). Pick one before any of them merges.

## Open P0/P1 (ranked)
1. brain-23 (P1, cloud/hobby-gaps) 'all the way up/down' becomes a ±25/±15 delta — orchestrator.py:443-462
2. brain-16 (P1, main + cloud/brain-4) abs_level misreads relative requests ('down a bit at 3 pm' -> 3; brain-4 'up 20%' -> 20) — orchestrator.py abs_level
3. brain-21 (P1, cloud/hobby-gaps) brightness delta always fails, HandsKit needs level — Skills.swift:361
4. brain-22 (P1, cloud/brain-4) history default dsl vs [ok] few-shot; echoed lines are executable — planner.py:224, cli.py:266
5. brain-17 (P1, main) compound check adds serial route passes before every 'and' utterance — orchestrator.py:336
6. brain-15 (P1, main) route parity gate disabled by stale v1 samples — ml/tests/test_route_parity.py:60-91

## Open P2
brain-14 (confirm token carry-over), brain-18 (BatchCutter bare skills), brain-12 (pending ASK capture), brain-19 (no_text_target), brain-8 (last_action quoting). Repros are in tests/test_brain_pass16.py; pass-18/19 repros are in tests/test_brain_pass18.py and tests/test_brain_pass19.py.

## Highest-leverage next moves
1. Choose ONE relative-control scheme (brain-4 / hobby-gaps / brain-5 brief) and have abs_level cover 'all the way', 'max' and 'full' (brain-23, brain-16).
2. Ship HandsKit set_brightness delta before any brain branch emits delta (brain-21).
3. brain-4: keep history=marked, or render the few-shot through history() and make action_line reject '-> ok'. Record tuned planner_offline numbers (brain-22).
4. brain-16 on brain-4: treat 'up/down … N%' as relative and reject 'at N pm'.
5. brain-15: land parity_300.jsonl on main and make parity failures fail the test.
