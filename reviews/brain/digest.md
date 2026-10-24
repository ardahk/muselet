# brain lane digest — pass 24 (2026-10-24T11:15Z)

Reviewed: main d502b78 (merged cloud/hobby-gaps: calculator execution + read-back, relative controls; serve_brain r2 router
with its own ARGS, tau .45; evals/route_v1_clean.jsonl 103/140), wip/local c7c04ce (= main), cloud/hobby-gaps 156556e,
cloud/data-pipeline 19737e1 (evalcheck contamination gate; outside lane), cloud/decisions 6d395df (training; outside lane).
Tests: main 1096 passed / 2 skipped / 0 xfailed.

Open: P0 0, P1 5, P2 5.  Resolved this pass: brain-23 on main.

## Open P1 (ranked)
1. brain-25 (new) calculator delivery: `act open Calculator` has no expect; HandsKit returns ok even if activation is ignored, and
   the brain then posts `esc 1 1 shift+= 4 =` into the frontmost app (the user's document). reviews/brain/tests/test_brain_pass24.py.
2. brain-24 fuzzy path lookup: "trash invoice 2024" -> invoice 2023.pdf (orchestrator.py:599).
3. brain-16 abs_level: '3 pm' -> 3, 'volume 20%' after 'turn up' -> 20, 'for a min' -> 0, 'battery is full' -> 100.
4. brain-22 planner history `x -> ok` vs `[ok] x` few-shot; `press #4 -> ok` parses as an action.
5. brain-17 compound check runs serial route passes before speculative reuse.

## Next moves
1. Gate calculator keys on `expect app "Calculator"` (or open_app + not_frontmost) before the demo (brain-25).
2. Exact-only path matches for trash/move; fuzzy -> ASK (brain-24).
3. Anchor abs_level markers to the property and reject times/durations (brain-16).
4. dsl.action_line: reject `-> ok|failed` suffixes (brain-22).
5. Score the r2 router on route_v1_clean (103) rather than route_v1 (140) until the contamination check lands; serve_brain notes r2 self 1.000 on route_v1.
