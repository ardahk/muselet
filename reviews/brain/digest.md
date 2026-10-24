# Brain lane digest — pass 35 (2026-10-24T17:05Z)

main cf53292 = PR #25 (cloud/brain-7) + native-research + report + three data builder briefs. Main suite: 1222 passed,
2 skipped, 1 deselected (Linux-slow real-model test). New: cloud/comms 956d4ac (contacts-first messaging + email drafts,
1233 passed), cloud/report-2 (docs). Moved: cloud/decisions 43abfa3, cloud/data-pipeline f8b721a (training only).

Open: P0 0 | P1 9 | P2 9

## P1
1. brain-33 (new, wip/local) — snapshot says "on main@cf53292" but its ml/ + skills/ tree equals 7a10df1 (pre-brain-7):
   sites.py, compose_text.py, test_first_use_fixes.py deleted, orchestrator -348. The Mac serves a brain without
   brain-7 and a commit from there reverts PR #25.
2. brain-32 (new, comms) — comms calls contacts_search / messages_compose / messages_send; no branch implements them in
   HandsKit, so merged alone every "text <name>" ends "Couldn't search your contacts". Brain logic itself is right
   (never a raw name; ask on 0 / >1 matches; confirm after compose). 3 merge conflicts with main.
3. brain-25 — Calculator delivery can type into the wrong frontmost app (main).
4. brain-29 (now main) — installed Zoom/Teams/Outlook open websites; failed `apps` RPC caches [] for 60 s.
5. brain-30 (now main) — 35B escalation: overlapping enables load two copies; "off" during load leaves it resident.
6. brain-24 — "trash invoice 2024" picks invoice 2023.pdf.
7. brain-16 — abs_level misreads "3 pm", "20%", "for a min", "battery is full".
8. brain-22 — planner history `x -> ok` vs few-shot `[ok] x`.
9. brain-17 — compound check serial route passes.

## P2
- brain-34 (new, decisions) — lazy import drops `decision.mlx_lm`; 4 test_args_model tests error on the branch.
- brain-31 — config_ack schema: main (brain-7) has no `ok`; app-ui shows "Not available" after a load.
- brain-27, brain-28 (sendgate gaps), plus older P2s (brain-8, 12, 14, 18, 19) unchanged.

## No findings
- comms: verbatim_handle (email / >=7-digit phone only), ranking tiers, ordinal/label/digit answers, retry caps,
  draft send re-checks app + window title and confirms; planner and routed send_message both go via comms.
- decisions choice_renderer.py is identical to main's AlphaChoiceRenderer (parity unaffected).
- data-pipeline f8b721a, report-2: outside the lane.

## Lead decision
- brain-7 vs app-ui escalation design + ack schema (carried from pass 34; brain-7's half is now on main).
- Who builds the three comms HandsKit RPCs, and land them with comms.
