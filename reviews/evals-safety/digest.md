# evals-safety digest — pass 28 (main@04c3930)

Open: P0 0 · P1 6 · P2 8

## Open P0/P1 (ranked)
1. **-30 (now on main)** grounded `click "<target>"` confirms only if the planner's description contains a danger word ('the paper plane icon' -> no confirm). The grounder is on by default, and the prompt now steers blind windows to click "<description>". orchestrator.py:1319-1336.
2. **-25** live document guard skips 9/43 cases and drops skips from the denominator.
3. **-6** Enter-to-send confirm fallback only covers Messages/Mail/Slack (orchestrator.py:1286).
4. **-11** `done` accepted without a harness final-state check.
5. **-26** main-final near-dups 37/140 route_v1 and 10/43 live_t1. The pitch now uses route_v1_clean with disclosure; serve_brain.sh:6 still cites full-set 1.000; no live_t1 clean subset.
6. **-23** spend guard latch plus billing lag.

P2: -8, -12, -20, -21, -22, -24, -28, -31 (new: planner holdout-1 is now tuned-on; report holdout2).

## Next moves (max 5)
1. Confirm grounded clicks on blind windows when the goal or app is send/delete/post-like (-30).
2. Count skips in the live denominator, or narrow the document guard (-25).
3. Add a live_t1 clean subset or caveat; fix the serve_brain.sh:6 comment (-26).
4. Check or reset runs/tinker_guard.state before the next Tinker job (-23).
5. Report planner holdout2 with the prompt sha (-31).
