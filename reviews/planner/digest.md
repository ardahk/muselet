# planner lane — pass 20 (wip 4350185; data-pipeline 8881d38 didn't touch this lane)

Pass 20: no new findings. wip adds the timers/timers_cancel RPCs, set_brightness delta, truthful launches (not_frontmost), media keys in `keys`, and Calculator as a keystroke app for type_text. Brain dsl.py passes any `keys` combo through, so media keys work from the planner. For planner-24, the safest fix is to have _deliver_calc call skill type_text instead of global keys.

## Pass 19 notes

Pass 19: no new findings. brain-5 adds routed-skill arg fixes, compound->planner handoff, a path resolver and a full-path move_to_trash confirm, and its 77 tests pass. wip's HandsKit launches now verify the app is frontmost (open_app, open_url, open_folder), and the `open` op waits up to 2 s, which partly mitigates planner-24. cloud/decisions only touches its spec and data pipeline. Merge risk: brain-4 and brain-5 both rewrite orchestrator.py, so re-run the planner-20 repro after merging both.

## Pass 18 notes

Resolved: planner-23 on hobby-gaps (the volume fast path now requires volume context; repro re-run).
Reviewed: brain-4 dfb66a3 (history default changed to dsl; the opt-in escalation planner takes over at fail_streak 2 and stops after it fails twice). It looks correct, and 78 tests pass with the mlx stub. main c39df67 widens a holdout accept pattern to `type #2 "github.com" enter`. That answer is legitimately valid, but grader edits made after holdout results are seen should be logged, to keep the holdout honest.

## Open P1 (ranked)
1. planner-24 P1 (hobby-gaps) — calculator keys are sent as global keys before Calculator is confirmed frontmost, so they can land in the user's document — ml/src/brain/orchestrator.py L719-724
2. planner-20 P1 (main) — the harness's own `done` rejection counts toward the "I'm stuck" guard. Fixed on cloud/brain-4, not yet on main — ml/src/brain/orchestrator.py
3. planner-6 P1 (main) — Premiere is still keyboard shortcuts only, with the 8766 bridge not connected — app/Sources/HandsKit/Skills.swift L256-261, 756

## Highest-leverage next moves
- Merge cloud/brain-4 (closes planner-20), and copy reviews/planner/tests/test_planner20_done_reject_streak.py into ml/tests.
- hobby-gaps: put `expect app "Calculator"` on the open action and abort before any keys if it fails.
- brain-4: build OpConstraint at warmup, for both the main and the escalation planner (planner-25).
- Premiere: add an expect to each premiere_command, or connect the bridge.
