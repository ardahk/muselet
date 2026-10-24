# evals-safety digest — pass 32 (main@b625ceb)

Open: P0 0 · P1 4 · P2 9   (-23 downgraded to P2: latch fixed, billing-lag headroom remains)

## Open P0/P1 (ranked)
1. **-30** grounded `click "<target>"` confirms only if the planner's description has a danger word ('the paper plane icon' -> no confirm). The grounder is on by default and the prompt steers blind windows to it. orchestrator.py:1319-1336.
2. **-25** live document guard skips 9/43 cases and drops skips from the denominator (matters for the morning live runs).
3. **-6** Enter-to-send confirm fallback only covers Messages/Mail/Slack (orchestrator.py:1286).
4. **-11** `done` accepted without a harness final-state check.

P2: -8, -12, -20, -21, -22, -23, -24, -28, -31.

## Next moves (max 5)
1. Merge cloud/brain-6 780f49d: it fixes -30 (grounded-click gate: composer context, payment context, AX label, fail-closed OCR) and -6 (sendgate.enter_sends).
2. Count skips in the live denominator, or narrow the document guard, before the morning runs (-25).
3. Extend the Enter-confirm app list to Discord/WhatsApp/Teams/web composers (-6).
4. Report planner holdout2 with the prompt sha (-31).
5. Leave Tinker headroom for billing lag on any large late run (-23).

Pass 31 also checked: pitch-3/4 contamination tables merged to main. data-pipeline 512cce0 compares CJK by character and never matches evals that normalize to empty (it2 v3: DeskMind 0, sealed-r4 0); that closes the CJK blind spot noted in pass 30.

Pass 32: cloud/brain-6 780f49d fixes -6 and -30 (verified by probes; test_sendgate needs mlx, so not run here). Both stay open on main until merge.
