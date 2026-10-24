# Cloud builder: comms (messages to real contacts, email drafting) — Muselet

Repo `ardahk/muselet`. Read `AGENTS.md` first (safety rules, the protocol, `ml/src/brain/sendgate.py`). Branch
`cloud/comms` from main, one PR, Python only (`ml/`). Linux has no macOS, so test with fakes. A local agent implements
the HandsKit side of the RPC contract below. Don't edit `app/`, `prompts/` or `skills/catalog.json`, except to add the
hidden skill entries listed in section 2.

## User report (live, this morning)
"send a message to arda" went straight to Messages and sent the text to the literal handle "arda", a contact that
doesn't exist. The user wants this flow instead:
1. Search Contacts first.
2. Open Messages on screen with that person's conversation and the text visible in the compose field.
3. Ask "Send this to Arda Hoke?".
4. Only on yes, send.
If several contacts match, ask which one, so the user can answer by voice. If none match, ask for the number or email.
Never message a raw name.

## 1. send_message flow (orchestrator, routed skill AND planner `skill send_message`)
- Resolve `to` with the new RPC `contacts_search {query, limit: 5}` →
  `{matches: [{id, name, handles: [{kind: "phone"|"email", value, label}]}], ms}`.
  - Phone numbers or emails spoken verbatim skip the search.
  - Fuzzy name match: first name, full name, nickname.
  - 0 matches → ASK "I couldn't find <name> in your contacts. What's their number or email?"
  - More than one match, or one contact with several handles → ASK with up to 3 choices, distinguished by full name and
    handle label (e.g. "Arda Hoke (mobile) or Arda Smith?"). The voice answer is resolved by code: ordinal (first,
    second), a name fragment, or a label.
- Preview: `messages_compose {handle, body}` opens Messages with that recipient and the body in the compose field,
  without sending, and returns `{ok, frontmost, window_title, body_visible}`.
- Then `confirm "Send '<body>' to <Full Name> (<handle label>)?"`. Only on yes, send with `messages_send {}` (presses
  send in the composed window and returns `{ok, sent: bool}`). On no, leave the draft and say "Left it as a draft".
- Trace each stage. Tests for 0, 1 and many matches, ordinal and fragment answers, the verbatim-number path, no, and
  timeout.

## 2. Email drafting (new hidden brain skill `draft_email`)
Add to skills/catalog.json, with `"router": false` (the brain-7 PR adds support for this flag; coordinate by rebasing
on it, and if it isn't merged yet, add the same exclusion yourself): `draft_email {to?, about?, reply?: bool}`,
executor brain, risk safe. The user wants "draft an email to my coworkers saying hello" and "help me reply to this
email".
- Context: when reply is set or an email is open, read it through `observe` (Mail app AX, or Gmail in the default
  browser through web AX; Chrome needs the web_ax_pending re-observe). If the AX text is empty, use the `ocr` RPC on
  the window.
- Write the draft with the planner's model (base 4B; the 35B when escalation is on): ≤ 120 words, matching the
  thread's tone, signed only if the user's name is known. Never invent facts.
- Target:
  - Mail app (if it's frontmost, or the user said "mail"): `compose_email` / Reply.
  - Gmail web (if a Gmail tab is frontmost or the user said gmail): open Compose or Reply, then type into the body.
  - Sign-in page → ASK the user to sign in.
- Never send. End with a bubble: "Draft ready. Say send to send it" (sending then goes through the confirm path).
- Tests with fakes for each path.

## 3. RPC contract (put it in `ml/src/brain/comms.py` docstrings; the lead adds it to AGENTS.md)
`contacts_search`, `messages_compose`, `messages_send` as above. Errors: `contacts_denied` (no Contacts permission →
bubble "Allow Contacts for Muselet in System Settings"), `not_frontmost`, `screen_locked`.
Reply with the PR link, the test count and the exact Swift behavior you assumed for each RPC.
