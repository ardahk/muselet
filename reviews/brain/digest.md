# Brain lane digest — pass 39 (2026-10-24T20:40Z)

main 026aff0 = 7065dd3 + data-planner/data-route/report-2 PRs + HandsKit comms RPCs (2374867) + Contacts permission
(026aff0) + relative-path refusal / verbatim-only send_message in hands (b6cca9d) + 65 s contacts_search timeout.
Product suite 1257 passed, 2 skipped; review suite unchanged (27 failed / 25 passed).
wip/local 98d1401: compose error bubbles (recipient_unverified, no_text_target, bad_handle) + Observe/MessagesCompose tweaks.
cloud/brain-8 4546d09: suite 1342 passed, 2 skipped; old repros unchanged (27 failed).

Open: P0 0 | P1 8 | P2 9

## Resolved
- brain-32 — RPC.swift:199-213@026aff0 dispatches contacts_search / messages_compose / messages_send; schemas match comms.py.

## P1
1. brain-35 (brain-8, new) — permission gate reads the pre-batch observation: `press #4` raises a TCC prompt and the
   same batch's `keys return` goes to it. Diff-built observations also skip the plan-time gate.
2. brain-25 — Calculator delivery can type into the wrong frontmost app.
3. brain-29 — installed Zoom/Teams/Outlook open websites; failed `apps` RPC caches [] for 60 s.
4. brain-30 — 35B escalation: overlapping enables load two copies; "off" during load leaves it resident.
5. brain-24 — "trash invoice 2024" picks invoice 2023.pdf (brain-8 path normalization does not touch the fuzzy step).
6. brain-16 — abs_level misreads "3 pm", "20%", "for a min", "battery is full".
7. brain-22 — planner history `x -> ok` vs few-shot `[ok] x`.
8. brain-17 — compound check serial route passes.

## P2
- brain-36 (brain-8, new) — "not too much" / "by the way" force a ±30 volume step.
- brain-34 (decisions), brain-27, brain-28, brain-8, 12, 14, 18, 19 unchanged.

## No findings
- brain-8 absolute paths (aliases, leading my/the/on/in/to, trailing "folder", home-relative only if it exists, ask
  otherwise), web answer (page is data, 12-word cap, NOT_FOUND fallback, offline unchanged).
- planner-demos: teacher runner (paid APIs, lead-run) reusing render.messages; outside the lane.

## Lead decision
- None. Fix brain-35 before merging brain-8 (it is the P0 permission gate).
