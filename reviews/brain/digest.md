# brain lane digest — pass 23 (2026-10-24T11:00Z)

Reviewed: main 26ff05b (merged PR #17 cloud/brain-5, argfix kill/cut/stop polarity, v2 route parity reference), wip/local 2c79363 (= main),
cloud/hobby-gaps 861b991 (merge of main d514300 only), cloud/data-pipeline eae3b7e (plan doc), cloud/decisions 91a62c2 (training labeler; outside lane).
Tests: main 1085 passed / 2 skipped / 0 xfailed (parity gate live: test_route_parity 52 passed); hobby-gaps 936 passed / 51 xfailed.

Open: P0 0, P1 5, P2 5.  Resolved this pass: brain-15 (route parity gate re-armed on main).

## Open P1 (ranked)
1. brain-24 (main) fuzzy path lookup: "trash invoice 2024" resolves to invoice 2023.pdf (orchestrator.py:599@26ff05b). Now in the demo path.
2. brain-16 (main) abs_level: "down a bit at 3 pm" -> 3, "volume 20%" after "turn up" -> 20, "for a min" -> 0, "battery is full" -> 100.
3. brain-22 (main) planner history `x -> ok` vs `[ok] x` few-shot; `press #4 -> ok` still parses as an action.
4. brain-23 (hobby-gaps) "all the way up" -> +25; branch now conflicts with main in orchestrator.py/catalog.py.
5. brain-17 (main) compound check runs serial route passes before speculative reuse.

## Next moves
1. pathfind: exact matches only for trash/move/rename; fuzzy hits must ASK with the candidate name (brain-24).
2. abs_level: anchor min/max/full/N% to the property word and reject times/durations (brain-16); repros in reviews/brain/tests/test_brain_pass{16,18,20}.py.
3. Make dsl.action_line reject `-> ok|failed` suffixes or align the few-shot with dsl history (brain-22).
4. When rebasing hobby-gaps on main, keep brain-5's relative scheme and drop the _run_skill overrides (brain-23).
5. Speculative-route reuse before the compound split (brain-17).

Notes (no findings): argfix ec91b20 adds kill/cut/shut down/stop -> off for wifi/bluetooth; mixed-polarity utterances still return None, and
"cutting out" doesn't match `\bcut\b`.
