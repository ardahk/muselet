# Brain lane digest — pass 74 (2026-10-25T06:24Z)

Open: **P0 0 / P1 12 / P2 17**. New: brain-57, brain-58 (cloud/agentic-apps). Fixed: brain-51. Moved to main: brain-54, brain-55, brain-56. Worse on main: brain-50.

## Branches
- **main e2f7e5e**: merged premiere-route-fix, agentic-loop (incl. dc7a063 Spotify click ban), mac/fix-thinking, a615f00 timer controls via the planner, 4cf1a37 timer criteria in criterion().
- **wip/local 3f8e2f8**: snapshot on main; lane identical.
- **cloud/agentic-apps 523d2c1** (new, on pre-merge main): 12 app skills go through the planner by default -> brain-57, brain-58.

## New
- **brain-58 (P1)**: agentic send confirm names the parsed recipient/body, not what was typed or the open chat. Repro: planner types "running late, sorry" into Mom's chat; confirm says `Text Caleb Kawano: "I'll be there in ten"?`.
- **brain-57 (P1)**: --agentic-apps defaults on; skills hidden from a LoRA trained to call them; repeated disabled skill runs 12 planner turns (no strike). Repro fails on agentic-apps.

## Rechecks
- brain-51 fixed on main. brain-50: pass68 repro now fails 2/2 on main. brain-54/55 repros fail on main. brain-56: Spotify superseded by dc7a063, other library apps still affected.
- All other open findings unchanged.

## Tests (MLX stub, Linux)
- main, wip/local: 18 failed (MLX-only) / 2357 passed. agentic-apps: 19 failed (18 MLX-only + stale make_planner stub in test_planner_think) / 2375 passed.
- Review repros: main/wip 49 failed / 52 passed (+2 brain-50, +3 brain-54, +4 brain-55 on main); agentic-apps 45 failed incl. 2 new.
