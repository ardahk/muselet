# Brain lane digest — pass 38 (2026-10-24T20:20Z)

main 7065dd3 = fb2cfd0 + cloud/comms (6885b7c) + cloud/app-ui (e150506) + live-suite grader fixes (d421c00) +
cloud/builder_brain8.md. Brain code on main now equals cloud/comms@c94a407 except a protocol.py comment.
Product suite 1257 passed, 2 skipped; review suite unchanged (27 failed / 25 passed).
wip/local e29ea7c = main@d421c00 + app/Sources/HandsKit/Contacts.swift + MessagesCompose.swift (uncommitted Swift side of comms).

Open: P0 0 | P1 8 | P2 8

## P1
1. brain-32 (now on main) — comms calls contacts_search / messages_compose / messages_send; main's HandsKit has none,
   so every "text <name>" ends "Couldn't search your contacts". wip/local's Swift files match comms.py's schema, but
   RPC.swift@e29ea7c has no case for the three methods (switch at 70-206 falls to `unknown method`). Wire them in.
2. brain-25 — Calculator delivery can type into the wrong frontmost app.
3. brain-29 — installed Zoom/Teams/Outlook open websites; failed `apps` RPC caches [] for 60 s.
4. brain-30 — 35B escalation: overlapping enables load two copies; "off" during load leaves it resident.
5. brain-24 — "trash invoice 2024" picks invoice 2023.pdf.
6. brain-16 — abs_level misreads "3 pm", "20%", "for a min", "battery is full".
7. brain-22 — planner history `x -> ok` vs few-shot `[ok] x`.
8. brain-17 — compound check serial route passes.

## P2
- brain-34 (decisions) — lazy import drops `decision.mlx_lm`; 4 test_args_model tests error.
- brain-27, brain-28 (sendgate gaps), brain-8, 12, 14, 18, 19 unchanged.

## Notes
- builder_brain8 item 2 normalizes move_to_trash.path; brain-24 (fuzzy >=0.88 match on the trash path) sits in the
  same resolver, so it is cheap to fix in that PR. Item 3 (degree words override model delta) does not cover brain-16.
- app-ui on main: config_ack parsing already verified in pass 36 (brain-31 resolved).

## Lead decision
- None new. Land the Swift RPCs (plus RPC.swift dispatch) on main soon: messaging is broken on main until then.
