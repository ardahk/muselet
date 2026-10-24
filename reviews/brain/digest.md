# brain lane digest — pass 22 (2026-10-24T10:45Z)

Reviewed: main d514300 (merged PR #15 cloud/brain-4 + HandsKit batch 5 + tools/serve_brain.sh), wip/local b63699f (= main tree),
cloud/brain-5 b752261 (not_frontmost handling + merge of main), cloud/data-pipeline f13aa6d (export untie lm_head, eval fix).
Tests: main 914 passed / 2 skipped / 51 xfailed; brain-5 1033 passed / 2 skipped / 51 xfailed.

Open: P0 0, P1 6, P2 5.  Resolved this pass: brain-21 on main (Swift brightness delta merged).

## Open P0/P1 (ranked)
1. brain-24 (P1, brain-5) fuzzy path lookup picks `invoice 2023.pdf` for "trash invoice 2024" (orchestrator.py:599@b752261).
2. brain-16 (P1, main + brain-5) abs_level: main now inherits brain-4's version — "down a bit at 3 pm" -> 3 and "turn up the volume 20%" -> 20;
   brain-5 adds "for a min" -> 0, "battery is full" -> 100.
3. brain-22 (P1, now on main) planner history default `dsl` (`press #4 -> ok`) vs `[ok]` few-shot; history lines still parse as actions. Shipped as recommended by tools/serve_brain.sh.
4. brain-23 (P1, hobby-gaps) "all the way up" becomes +25 (brain-5 is correct).
5. brain-17 (P1, main) compound check runs serial route passes before speculative reuse.
6. brain-15 (P1, main) test_route_parity xfails all 51 cases (v1 samples file).

## Next moves
1. Before merging brain-5: ASK (don't auto-pick) on fuzzy path matches for destructive ops; anchor min/max/full to the controlled property.
2. Reject incidental times/durations/percent-after-direction in abs_level (brain-16) — now in the demo path on main.
3. Either revert history default to `marked` or make dsl.action_line reject `-> ok|failed` suffixes (brain-22).
4. Land parity_300.jsonl / v2 samples on main to re-arm the parity gate (brain-15).
5. Drop hobby-gaps' _run_skill relative overrides; brain-5's 10/30 scheme follows the brief.

Notes (no findings): brain-5 not_frontmost path returns a single fail bubble and terminates the planner batch (orchestrator.py:1066-1072, 1396);
data-pipeline untie_lm_head yields an untied lm_head that main's split_model already supports; serve_brain.sh uses base ARGS with trained router as documented.
