# hands — digest (pass 14: main bb494af, wip/local c85a000, cloud/bench f584cb2, cloud/data-pipeline 70b7d1b; no new app/ code since pass 11)

Resolved: hands-1 to hands-9 and hands-11 to hands-14. hands-15 superseded.
Pass 11: main's app/ tree now equals wip/local 64dd1cb (already reviewed). wip/local 38768f3 has no app/ or brain-protocol changes, and cloud/data-pipeline 1d65818 does not touch app/. No new findings. Pass 12: cloud/bench 2c57d7f only merged main into its app/ code (bench safety cases); no new app/ code.

## Open P0/P1 (ranked)
None.

## Highest-leverage next moves
- hands-10 (P2): cap the act lead in Act.swift:269-271 with `min(lead, cursor_lead_ms/1000)` as RPC.swift does for skills. Up to 100 ms per act, up to 0.5 s per 5-action batch.
- Residual from hands-12 (not filed): `appears` still uses substring matching and counts other already-open windows of the target app. Watch for false passes in the live T1/T2 suite.
