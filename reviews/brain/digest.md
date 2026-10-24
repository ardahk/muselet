# brain digest — pass 21 (2026-10-24T10:30:00Z)

Pass 21: wip/local 4350185 (Swift only) adds the set_brightness delta branch, so brain-21 is RESOLVED (Skills.swift:418-439). It also adds the timers/timers_cancel RPCs and media keys, with no brain-side contract break. cloud/data-pipeline 8881d38 changes only a docstring: ARGS trains on the answer only, and the think block is prompt, matching the runtime prefill. No findings. The other branches are unchanged since pass 20.


main 758a017 is unchanged. wip/local 630d661 changes only Swift (Launch, MediaKeys, Timers, Skills, TextTarget); it adds set_brightness `delta` to the docs and the arg check, but not to the executor (brain-21).
cloud/brain-5 003d1bb (live-suite fixes: vague deltas, on/off polarity, compound follow-ups, path resolve, Finder view, duration coercion): 949 passed, 2 skipped, 51 xfailed. It fixes 'all the way up/down' (passes the brain-23 repro). New P1 brain-24 is in path resolve, and brain-16 gets a new regression: any 'min' or 'full' sets an absolute level. The polarity lexicon, the follow-up 'open it' and the duration slot look correct.
cloud/decisions c08a96d (generic decisions data pipeline, SPEC): outside the runtime. render.py puts the target at choice_pos-1, which is correct. The pyproject change only adds the optional extra `decisions = [httpx==0.28.1]`. No findings.
MERGE NOTE: there are still three relative-control schemes (brain-4 rel_delta, hobby-gaps ±15/25, brain-5 argfix 10/30). brain-5 follows the lead's brief, so drop the other two.

## Open P0/P1 (ranked)
1. brain-24 (P1, cloud/brain-5) fuzzy path resolve picks 'invoice 2023.pdf' for 'trash invoice 2024' — pathfind.py:144, orchestrator.py:504
2. brain-16 (P1, main + brain-4 + brain-5) abs_level misreads: 'down a bit at 3 pm' -> 3; brain-5 'for a min' -> 0, '…battery is full' -> 100 — orchestrator.py abs_level
3. brain-23 (P1, cloud/hobby-gaps) 'all the way up' -> +25 (fixed on brain-5) — orchestrator.py:443-462
4. brain-22 (P1, cloud/brain-4) history=dsl vs '[ok]' few-shot; echoed lines are executable — planner.py:224
5. brain-17 (P1, main/brain-5) serial compound routes; brain-5 now sends an imperative 2nd clause to the planner — orchestrator.py:386,678
6. brain-15 (P1, main) route parity gate disabled by stale v1 samples — ml/tests/test_route_parity.py

## Open P2
brain-14, brain-18, brain-12, brain-19, brain-8. Repros are in tests/test_brain_pass16.py; pass 18-20 repros are in tests/test_brain_pass18.py, test_brain_pass19.py and test_brain_pass20.py.

## Highest-leverage next moves
1. brain-5: accept only exact matches for move_to_trash; fuzzy hits go to the ASK (brain-24).
2. brain-5: anchor min/max/full to the control ('to the max', 'full volume'), not anywhere in the sentence (brain-16).
3. Land wip/local's set_brightness delta together with brain-5, so that relative brightness works on main.
4. Merge brain-5's relative scheme, and drop hobby-gaps' _run_skill override (brain-23) and brain-4's rel_delta.
5. brain-15: land parity_300.jsonl on main and make parity failures fail the test.
