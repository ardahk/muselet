# evals-safety digest — pass 29 (main@d7c192f)

Open: P0 0 · P1 6 · P2 8   (resolved this pass: -26; new: -32)

## Open P0/P1 (ranked)
1. **-30** grounded `click "<target>"` confirms only if the planner's description has a danger word ('the paper plane icon' -> no confirm). The grounder is on by default and the prompt steers blind windows to it. orchestrator.py:1319-1336.
2. **-32 (new)** default router it2 failed the repo's own contamination gate: DeskMind diag 1/13 (3/39 pitch runs), deskmind/dyn 16, HobbyLM r2/r3 1 each, route_v1 7. it2b passes 0. serve_brain.sh:2-12.
3. **-25** live document guard skips 9/43 cases and drops skips from the denominator.
4. **-6** Enter-to-send confirm fallback only covers Messages/Mail/Slack (orchestrator.py:1286).
5. **-11** `done` accepted without a harness final-state check.
6. **-23** spend guard latch plus billing lag.

P2: -8, -12, -20, -21, -22, -24, -28, -31.

## Next moves (max 5)
1. Confirm grounded clicks on blind windows for send/delete/post-like goals or apps (-30).
2. Serve it2b, or report DeskMind diag on the 12 clean tasks with disclosure (-32).
3. Count skips in the live denominator, or narrow the document guard (-25).
4. Check or reset runs/tinker_guard.state before the next Tinker job (-23).
5. Report planner holdout2 with the prompt sha (-31).
