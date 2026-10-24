# brain lane digest — pass 25 (2026-10-24T11:30Z)

Reviewed: wip/local 0db1681 (vs main: only ml/src/brain/generic_decide.py — MLX work moved to a dedicated worker thread),
cloud/data-pipeline 0c1ca3d (evalcheck also gates evals/external, 570 rows; it2b filter drops 9 route-train items; outside lane).
main d502b78 unchanged since pass 24 (1096 passed / 2 skipped).

Open: P0 0, P1 6, P2 5.

## Open P1 (ranked)
1. brain-25 calculator delivery: `act open Calculator` has no expect; HandsKit returns ok even if activation is ignored, and
   the brain then posts `esc 1 1 shift+= 4 =` into the frontmost app (the user's document). test_brain_pass24.py.
2. brain-26 (new, wip/local) GenericMLXDecider.__init__ hangs: the worker puts its init `None` on `_jobs` (generic_decide.py:156) and
   immediately reads `_jobs` itself (:161), takes its own None as the stop sentinel and exits; __init__ waits at :140 forever.
   20/20 hangs in test_brain_pass25.py. bench/systemone/cli.py:33 never gets a decider.
3. brain-24 fuzzy path lookup: "trash invoice 2024" -> invoice 2023.pdf (orchestrator.py:599).
4. brain-16 abs_level: '3 pm' -> 3, 'volume 20%' after 'turn up' -> 20, 'for a min' -> 0, 'battery is full' -> 100.
5. brain-22 planner history `x -> ok` vs `[ok] x` few-shot; `press #4 -> ok` parses as an action.
6. brain-17 compound check runs serial route passes before speculative reuse.

## Next moves
1. Gate calculator keys on `expect app "Calculator"` (or open_app + not_frontmost) before the demo (brain-25).
2. Separate init queue/Event in GenericMLXDecider before wip lands on main (brain-26).
3. Exact-only path matches for trash/move; fuzzy -> ASK (brain-24).
4. Anchor abs_level markers to the property and reject times/durations (brain-16).
5. dsl.action_line: reject `-> ok|failed` suffixes (brain-22).
6. Score the r2 router on route_v1_clean until the contamination check lands.
