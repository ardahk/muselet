# hands — digest (pass 18)

Open findings were re-verified on main 2920225 in pass 15: hands-1 to 9 and 11 to 14 are resolved, and hands-15 is superseded.
Pass 17: main 28dc259 and wip/local e1701a3 only change the bench and planner holdout set; there is no app/ or protocol change. cloud/brain-4 changes the orchestrator only for ROUTE/ARGS split and planner flags, with no new RPC shapes. cloud/hobby-gaps adds the calculator act path and change_volume/set_brightness routing; both skills exist in catalog.json and Skills.swift, and Combo supports every character calc.py emits.

Pass 18: main 758a017 and wip/local a3f82f1 have no app/ or protocol changes (pitch-2 merge, bench and live-runner fixes). The cloud/brain-4 dfb66a3 escalate-model change sends no new RPCs. cloud/hobby-gaps 929b931 hardens the calculator read-back, which still runs as one act per key (hands-16 updated).

## Open P0/P1 (ranked)
None.

## Highest-leverage next moves
- hands-10 (P2): cap the act ghost-cursor lead in Act.swift:271 with `min(lead, cursor_lead_ms/1000)`.
- hands-16 (P2, cloud/hobby-gaps): enter the calculator expression in one keystroke script or a multi-combo act. Today each key costs at least 120 ms of settle (9 acts for '1250+3', at least 1.08 s). Read the result with an in-process verify/observe, not a System Events tree walk.
- Not filed: `appears` still matches substrings and counts other already-open windows of the same app.
