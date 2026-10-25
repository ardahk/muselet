# Brain lane digest — pass 68 (2026-10-25T04:55Z)

Open: **P0 0 / P1 9 / P2 14**. New: brain-51. brain-50 worse on cloud/premiere-route-fix.

## Branches
- **main 82c9810** (from dc6f2f5): `observation_blind` now also treats AX trees with only window controls (close/minimize/zoom/full screen) as blind, so Spotify-style CEF apps go to screenshot + grounder. Empty trees stay blind; unlabeled elements don't count as chrome. No issue; worst case is an extra grounder pass on a dialog whose only control is "Close".
- **wip/local 5b656ef**: snapshot on main@82c9810; lane matches main.
- **cloud/premiere-route-fix 7769c32** (on dc6f2f5):
  - Fixes brain-51: removes the reassignment that sent draft_email args to premiere_edit.
  - Moves the Premiere pre-route to the top of handle_utterance, ahead of page-task and messaging. Combined with brain-50's broad matching, messages that mention export/cut/premiere now go to premiere_edit (tests/test_brain_pass68.py: pass on main, 2/2 fail on branch).

## New
- **brain-51 (P2, main, reachability low)**: route-plan fallback (orchestrator.py ~993-1003) dispatches draft_email args as premiere_edit, which fails op validation. Missed in pass 67; fixed on premiere-route-fix.

## Rechecks
- brain-50 open on main (pass67 repro 4/4 fail) and worse on premiere-route-fix.
- brain-47, brain-48, brain-49 still fail on main. brain-22, brain-42, brain-43 unchanged.

## Tests (MLX stub, Linux)
- main: 18 failed (MLX-only), 2328 passed, 2 xfailed. Review repros: 33 failed / 52 passed (+4 = pass67 now counted); pass68 2 passed.
- premiere-route-fix: 18 MLX-only, 2327 passed. Review repros 33 failed; pass68 2 failed.
