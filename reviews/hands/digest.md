# hands — digest (pass 9: main 76a03c1, wip/local 34ddf5f; new cloud/advisor-3, brain-3, finance-3 do not touch app/)

Resolved: hands-1 to hands-9 and hands-11 to hands-14. hands-15 superseded.
Pass 9 reviewed: fixed-source AppleScript handlers (AppleScript.swift: no source splicing, compiled once), the no_text_target guard on `type` (TextTarget.swift), and the window-pick fallback with a 0.8 s wait right after launch (Observe.swift). No new P0/P1.

## Open P0/P1 (ranked)
None.

## Highest-leverage next moves
- hands-10 (P2): cap the act lead in Act.swift:269-271 with `min(lead, cursor_lead_ms/1000)` as RPC.swift does for skills. Up to 100 ms per act, up to 0.5 s per 5-action batch.
- Residual from hands-12 (not filed): `appears` still uses substring matching and counts other already-open windows of the target app. Watch for false passes in the live T1/T2 suite.
