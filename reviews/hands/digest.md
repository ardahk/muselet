# hands — digest (pass 39)

Reviewed: main 026aff0 (Swift side of the comms RPCs, Contacts plist and entitlement, the 65 s contacts timeout, relative-path refusal in file skills, verbatim-only send_message), wip/local 98d1401 (panel-send and observe own-pid fix, stricter Messages recipient check), cloud/brain-8 4546d09 and cloud/planner-demos 84798ec.

Open: 0 P0, 2 P1, 3 P2. Static analysis only; no macOS runtime here.

Resolved: hands-19 (RPCs wired with one shared composer), hands-21 (NSContactsUsageDescription and addressbook entitlement added), hands-22 (65 s brain timeout, longer than Swift's 60 s wait).

- P1 hands-23 (new; main, fixed on wip/local): on main, messages_compose matches the recipient against every string in the Messages window, sidebar included. A name in the conversation list can verify the wrong chat, and the confirmed send then goes there. wip/local restricts the check to the title, the header and the To field, and runs it before writing.
- P1 hands-18 (main, fixed on wip/local): panel example prompts may act on Muselet. wip/local's sendFromPanel and the own-pid fallback in observe look correct.
- P2 hands-20: send_draft doesn't re-check the draft window after the confirm.
- P2 hands-16: the calculator types one keystroke per RPC.
- P2 hands-10: act ignores cursor_lead_ms (Act.swift:348).
- Not filed: `appears` matches substrings and counts other windows of the same app.

Checked and fine: brain-8 uses `ocr {path}` and `{region}` (both accepted, RPC.swift:163-171), screenshot and observe, and the permission-prompt gate is brain-only. PathAlias.checked refuses relative paths with a `relative_path` code. planner-demos doesn't touch my lane.

Lead decision: merge wip/local's Messages recipient check and panel fix to main before demoing texting.
