# hands — digest (pass 38)

Reviewed: main 7065dd3 (merged cloud/comms 6885b7c and cloud/app-ui e150506, plus a live-suite grader fix and the brain-8 brief) and wip/local e29ea7c (adds HandsKit Contacts.swift and MessagesCompose.swift). Other branches haven't moved since pass 37.

Open: 1 P0, 3 P1, 4 P2. Static analysis only; no macOS runtime on this VM.

- P0 hands-19 (raised from P1; now on main): send_message always calls `contacts_search` (comms.py:369), but RPC.swift has no case for it and returns "unknown method" (RPC.swift:205-206). Texting is broken on main. wip/local's Contacts.swift and MessagesComposer aren't dispatched from RPC.swift yet.
- P1 hands-21 (new, wip/local): the Info.plist that build_app.sh generates has no NSContactsUsageDescription, so the first CNContactStore access will be killed by TCC.
- P1 hands-18 (now on main): panel example prompts may act on Muselet itself (AppDelegate.swift:242; observe has no own-pid fallback).
- P2 hands-22 (new): the brain's 5 s contacts_search timeout is shorter than the first-use permission prompt (Swift waits up to 60 s).
- P2 hands-20 (now on main): send_draft doesn't re-check the draft window after the confirm.
- P2 hands-16: the calculator types one keystroke per RPC.
- P2 hands-10: act ignores cursor_lead_ms (Act.swift:348).
- Not filed: `appears` matches substrings and counts other windows of the same app.

Checked and fine: the wip MessagesComposer.send gate re-checks frontmost, same window and an unchanged draft, posts one Return, then reads back that the field emptied. Compose fills the field through AX and never sends keystrokes, and it verifies the recipient. Error replies carry `result`.

Lead decision: wire the three comms RPCs into RPC.swift and add NSContactsUsageDescription before the demo. Otherwise texting on main fails, or crashes the app once the RPCs are wired.
