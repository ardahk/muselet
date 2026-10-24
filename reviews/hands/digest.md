# hands — digest (pass 8: main 4a74659, wip/local 85c73ed)

Resolved: hands-1 to hands-9 and hands-11 to hands-14. hands-15 superseded by activation-time web AX prewarm.

## Open P0/P1 (ranked)
None.

## Highest-leverage next moves
- hands-10 (P2): in Act.swift:259-261, cap the act lead with `min(lead, cursor_lead_ms/1000)` as RPC.swift already does for skills. This saves up to 100 ms per act on long flights (planner batches of 5 actions: up to 0.5 s).
- Residual from hands-12 (not filed): `appears` still uses substring matching and counts other already-open windows of the target app. Watch for false passes in the live T1/T2 suite.
