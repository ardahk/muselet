# Brain lane digest — pass 70 (2026-10-25T05:20Z)

Open: **P0 0 / P1 9 / P2 15**. No new findings. brain-52 moved from wip/local onto main.

## Branches
- **main e425cad** merged #86 (3678b4f, "P0: screen-context gating, open-ended ask guard, Clock wheel keyboard fallback"). Lane product code is identical to wip/local c156d18 reviewed in pass 69; only ml/tests/test_fallback_planner.py was updated (new "On-screen text" label; ask test relaxed to `planner.calls >= 2`).
- **wip/local 80c871c**: snapshot on main@82c9810, so its lane matches 82c9810 (predates #86). Nothing new to review.
- Other branches unchanged.

## Rechecks
- **brain-52 (P2, now main)**: tests/test_brain_pass69.py fails 2/2 on main. The relaxed `>= 2` assertion hides the extra planner call seen in pass 69 rather than explaining it.
- brain-47/48/49/50 repros still fail on main; brain-51, brain-22/42/43 and older findings unchanged (code paths not touched by #86).

## Tests (MLX stub, Linux)
- main: 18 failed (same MLX-only set) / 2334 passed / 109 skipped / 2 xfailed.
- wip/local: 18 failed (MLX-only) / 2328 passed.
- Review repros: main 35 failed / 54 passed (+2 = brain-52); wip/local 33 failed / 56 passed.
