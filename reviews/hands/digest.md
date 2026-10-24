# hands — digest (pass 16; open findings re-verified on main 2920225 in pass 15)

All hands findings re-checked on main 2920225. Resolved on main: hands-1 to hands-9 and hands-11 to hands-14 (file:line in findings.jsonl, pass 15). hands-15 superseded. None of them exists only on a branch: all the Swift batches are on main.
Main's app/ code is unchanged since bb494af (reviewed in passes 9-14), so there is no new app/ code to review in tonight's merges.

Pass 16: wip/local 3e03686, cloud/data-pipeline 5371185, cloud/decisions 3a865a0 and cloud/pitch-2 3303678 have no app/ changes and no server/protocol/orchestrator changes since their base. cloud/decisions only looks different from main because it forked before 2920225.

## Open P0/P1 (ranked)
None.

## Highest-leverage next moves
- hands-10 (P2): Act.swift:271 should cap the lead with `min(lead, cursor_lead_ms/1000)` (RPC.swift already does this for skills). Up to 100 ms per act, up to 0.5 s per 5-action batch.
- Residual from hands-12 (not filed): `appears` still uses substring matching and counts other already-open windows of the target app. Watch for false passes in the live T1/T2 suite and the offline planner bench.
