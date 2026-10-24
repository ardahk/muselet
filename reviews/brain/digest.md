# brain digest — pass 4 (2026-10-24T06:25Z)
Reviewed: wip/local e0bdc65, main e78f143, cloud/data-pipeline 153a01c, cloud/bench 14c7eb1, cloud/finance-2 f4ae461 (144 tests pass), cloud/advisor-2 ec98013; cloud/pitch has nothing in lane.
Suites at e0bdc65: catalog 9, dsl 45, orchestrator 9, planner_loop 14, finance 90, advisor 22 pass; route_parity 51 xfail (stale v1 artifact on wip).
Resolved this pass: brain-5 on wip/local (v2 parity 50/50 vs data-pipeline artifact) — main e78f143 still lacks the fix.

## Open P0/P1 (ranked)
1. brain-9  P0 Unsafe scripts execute without confirmation — orchestrator.py script_needs_confirm
2. brain-14 P1 One confirm unlocks every dangerous action in the batch — orchestrator.py:325/400
3. brain-11 P1 5th action expect dropped; DONE accepted unverified; scripts uncounted — planner.py:246, orchestrator.py:610
4. brain-13 P1 Speculative partial routes queue ahead of final route — orchestrator.py:257-267
5. brain-10 P1 Mute polarity inverted ("turn the sound back on" mutes) — orchestrator.py _coerce_args
6. brain-6  P1 engine.args runs on event loop, racing MLX worker — orchestrator.py:218,637
7. brain-3  P1 parse_duration wrong on compound/spoken numbers — decision.py
8. brain-4  P1 parse_datetime silently wrong ("at 3" -> March) — decision.py
(P2 open: brain-8 last_action quoting, brain-12 pending ASK captures next command)

## Highest-leverage next moves
- Copy the v2 route_render_samples.jsonl to wip and merge the brain-5 fix to main so the parity gate is live again.
- brain-9 + brain-14: confirm any script that clicks/presses/runs JS/opens files, and bind each confirm to one action.
- brain-13: cancel superseded spec routes and strip punctuation in the spec key, or speculation costs latency.
- brain-11: decode the 5th action's expect; verify DONE via `verify` RPC.
- brain-10/3/4: polarity-specific mute regex; parse via a number-word parser; ASK on ambiguous dates.
