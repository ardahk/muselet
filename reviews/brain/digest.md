# Brain lane digest — pass 37 (2026-10-24T19:35Z)

main fb2cfd0 = e56582b + cloud/bench-fix (harness timeout recovery, --run-pending, HobbyLM replay helper) + live_t1
final-state checks and "no user Finder windows" preconditions. wip/local 9ed6bc8 == main. No ml/, prompts/ or skills/
change, so every open finding stands (review suite 27 failed / 25 passed). bench/tests: 162 passed, 2 skipped.

Open: P0 0 | P1 8 | P2 8

Correction: brain-33 (pass 35) is withdrawn. I compared wip/local against a main that had already advanced to e56582b;
against cf53292 the snapshot was identical. Pass-35 "main@cf53292" results were measured on e56582b.

## P1
1. brain-32 (comms) — HandsKit has no contacts_search / messages_compose / messages_send on any branch; merged alone,
   every "text <name>" ends "Couldn't search your contacts". Merge conflicts with main are now resolved.
2. brain-25 — Calculator delivery can type into the wrong frontmost app.
3. brain-29 — installed Zoom/Teams/Outlook open websites; failed `apps` RPC caches [] for 60 s.
4. brain-30 — 35B escalation: overlapping enables load two copies; "off" during load leaves it resident.
5. brain-24 — "trash invoice 2024" picks invoice 2023.pdf.
6. brain-16 — abs_level misreads "3 pm", "20%", "for a min", "battery is full".
7. brain-22 — planner history `x -> ok` vs few-shot `[ok] x`.
8. brain-17 — compound check serial route passes.

## P2
- brain-34 (decisions) — lazy import drops `decision.mlx_lm`; 4 test_args_model tests error.
- brain-27, brain-28 (sendgate gaps), brain-8, 12, 14, 18, 19 unchanged.

## No findings
- bench-fix on main: the event-graded calendar case still drops its AppleScript precondition (unchanged
  behaviour, moved into _prepare_run_spec); it is gated by is_local_default(probe_bench_calendar()) instead.
- data-planner v2: validator OK (260 scenarios, 130/130 split, 0 failing, 0 goals shared with v1 or across splits);
  runner reuses planner_offline grade; no holdout goal appears in prompts/planner_fewshot.md.
- bench-fix, data-route: outside the lane.

## Lead decision
- Who builds the three comms HandsKit RPCs; land them with comms.
