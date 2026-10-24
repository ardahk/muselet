# evals-safety digest — pass 30 (main@fbd5aa0)

Open: P0 0 · P1 5 · P2 8   (resolved this pass: -32, the DeskMind hit was a CJK normalizer artifact)

## Open P0/P1 (ranked)
1. **-30** grounded `click "<target>"` confirms only if the planner's description has a danger word ('the paper plane icon' -> no confirm). The grounder is on by default and the prompt steers blind windows to it. orchestrator.py:1319-1336.
2. **-25** live document guard skips 9/43 cases and drops skips from the denominator.
3. **-6** Enter-to-send confirm fallback only covers Messages/Mail/Slack (orchestrator.py:1286).
4. **-11** `done` accepted without a harness final-state check.
5. **-23** spend guard latch plus billing lag.

P2: -8, -12, -20, -21, -22, -24, -28, -31.

## Next moves (max 5)
1. Confirm grounded clicks on blind windows for send/delete/post-like goals or apps (-30).
2. Count skips in the live denominator, or narrow the document guard, before the morning competitor/live runs (-25).
3. Merge pitch-4 (overlap disclosure table).
4. Check or reset runs/tinker_guard.state before the next Tinker job (-23).
5. Report planner holdout2 with the prompt sha (-31).
