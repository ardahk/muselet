# hands — digest (pass 41)

Reviewed: main 27ebd13 (create_event datetimes now carry the local UTC offset, HANDOFF docs), wip/local 4585ce4 (bench replay only), and the new cloud/comms-2 265c86d, cloud/clock-timers d060b5a, cloud/mascot-animal 238db23 and cloud/planner-retrieval 9786fa4. data-pipeline 34aff30 and decisions b78d778 don't touch my lane.

Open: 0 P0, 0 P1, 4 P2. Static analysis only.

- P2 hands-24 (new, comms-2): `messages_people` and `contacts_search{fuzzy}` don't exist in HandsKit on any branch. The flow falls back cleanly, but Messages-first ranking and fuzzy STT answers do nothing until the Swift side lands.
- P2 hands-20: send_draft doesn't re-check the window after the confirm (draft_email.py:454-470).
- P2 hands-16: the calculator types one keystroke per RPC.
- P2 hands-10: act ignores cursor_lead_ms.
- Not filed: `appears` matches substrings and counts other windows of the same app.

Checked and fine:
- main's create_event change: naive ISO datetimes used to fail the Swift parse (`.withInternetDateTime` needs an offset, Skills.swift:994-1001). The brain now sends `isoformat(timespec="seconds")` with the local offset, which that parser accepts.
- clock-timers: `/usr/bin/shortcuts` runs through Process with argv only (no shell). Both pipes are drained concurrently, with a 10 s timeout, then terminate, then SIGKILL. Failures fall back to a Muselet timer with `fallback_reason`. Worst case (list + run) is about 20 s, under the brain's 45 s skill timeout. timers_cancel error replies carry `result`. `shortcuts list` runs off the main thread in the panel. The Settings toggle is persisted.
- comms-2: send still goes through messages_compose/messages_send with the scoped recipient check. Mail opens are blocked for messaging goals.
- mascot-animal only changes art. planner-retrieval is brain-only, with no new RPCs.
- Not filed, low confidence: `Muselet Cancel Timer` cancels Clock's current timer whatever the id. With two Clock-backed records, cancelling by id may stop the other one. Worth a live check.

No lead decision needed. Before demoing comms-2's fuzzy names, the Swift side of its two RPCs must land.
