# hands — digest (pass 42)

Reviewed: main 3876f3a (HandsKit messages_people, fuzzy contacts_search, compose v2 with a 2 s window/field poll and the `name` param, windows probe, naive local ISO dates), wip/local 3cfa06d (local merge of comms-2 at cad2e67) and cloud/comms-2 c65ee70 (verb-first parsing restricted to message nouns; brain only).

Open: 0 P0, 0 P1, 4 P2. Static analysis only.

Resolved: hands-24. The Swift side of messages_people and contacts_search{fuzzy} is on main. comms-2 itself is merged only on wip/local so far.

- P2 hands-25 (new): a cold messages_people runs an AppleScript that makes one Apple Event per participant, with no timeout, on the serial RPC queue. My estimate is over 4 s on a large Messages history, so the brain gives up while the next RPC waits behind it. Fix: one bulk Apple Event, `with timeout`, and a prewarmed cache.
- P2 hands-20: send_draft doesn't re-check the window after the confirm.
- P2 hands-16: the calculator types one keystroke per RPC.
- P2 hands-10: act ignores cursor_lead_ms.
- Not filed: `appears` matches substrings and counts other windows of the same app.
- Not filed, safety residual: the recipient check accepts the contact name, and now also the brain-supplied `name`, as a case-insensitive substring of the header or To texts. A single-word name like "Alex" also matches a header "Alex Kim". This is limited by scoping to the header and To field (hands-23), but a handle match would be stricter. Worth a live check with two contacts who share a first name.

Checked and fine: Skills.iso now also accepts naive local datetimes. Fuzzy search enumerates contacts in-process, so it's cheap. The windows probe uses AX only, with a 0.5 s per-app timeout. compose error replies carry `contact_name_lookup` in `result`.

No lead decision needed.
