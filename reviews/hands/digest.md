# hands — digest (pass 40)

Reviewed: main dae4b26 (merged 68e76c6 with the scoped recipient check, panel ctx, own-pid observe fallback and error bubbles; brain-8 merge plus its review fix; live-suite manual cases; four new briefs), wip/local 972081d (main plus docs/HANDOFF.md), cloud/data-pipeline f6354d6 and cloud/planner-demos 9008990 (neither touches app/ or ml/src/brain).

Open: 0 P0, 0 P1, 3 P2. Static analysis only.

Resolved this pass: hands-23 (recipient check limited to title, header and To field, run before writing) and hands-18 (sendFromPanel plus the observe fallback).

- P2 hands-20: send_draft doesn't re-check the window after the confirm (draft_email.py:454-470).
- P2 hands-16: the calculator types one keystroke per RPC (orchestrator.py:1267).
- P2 hands-10: act ignores cursor_lead_ms (Act.swift:355).
- Not filed: `appears` matches substrings and counts other windows of the same app.

To check when the new briefs land: comms-2 (keep the scoped recipient check; any new RPCs must return `result`) and clock-timers via the Shortcuts CLI (shell output must stay bounded and failures must propagate).

No lead decision needed.
