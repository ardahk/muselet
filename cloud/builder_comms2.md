# Cloud builder: comms-2, messaging that understands people — Muselet (Python side)

Repo `ardahk/muselet`. Read `AGENTS.md` ("Model picks, code parses", protocol) and the `ml/src/brain/comms.py`
module docstring (RPC contract). Branch `cloud/comms-2` from main, one PR, Python only (`ml/`).
The Swift side is built on the Mac by the lead's team against the contract in section 6, so keep
that contract exact. Linux has no Metal: test with fakes (`ml/tests/fakes.py`, `ml/tests/test_comms.py`).
No `prompts/` or `evals/` edits.

## Evidence: the user's live attempts today (runs/traces, read by the lead)

| User said (STT text) | What happened | Wanted |
|---|---|---|
| "Send a message to Orda, Arda." | ARGS to="Orda" (STT self-correction); 0 contacts -> asked for a number | to="Arda" (last name after a correction) |
| "Send a message to Arda." (said again while the bot waited for a number) | the whole utterance was used as the name: contacts_search "Send a message to Arda" | treat it as a new command and restart the flow |
| "Send a text to Monica." | router ASK 0.89; generic ask, so the slot was lost | send_message to=Monica, missing body: "What should the message to Monica say?" |
| "Say hello." (the answer) | routed as type_text and typed into the IDE window | becomes the body of the pending message |
| "Send a hello message to Arda." | planner opened **Mail** and typed "hello" into To: and "Say hello." into Subject | iMessage to Arda with body "hello" (a "message" or "text" is never email) |
| "Send a text message to Arda saying hello Arda" | 5 matches; asked "Arda Didim, Arda Hoke, or H Arda?" | (fine) |
| "Ardaoke." then "Arda okay." (answers, STT for "Arda Hoke") | no option matched; failed | match Arda Hoke (whole-name fuzzy) |
| "Send a s text message to Caleb saying hello." | Contacts found Caleb Kawano; compose returned recipient_unverified because the name lookup inside Swift failed | pass the resolved name to compose (section 6) |

## Build

1. **Deterministic messaging parser, run before the router.** Use the same pattern as
   `draft_email.parse_request`: a redirect that runs before routing.
   - It returns `{to, body | None}` for clear messaging requests:
     - `send|shoot|drop (me)? (a|an)? (quick)? (text|message|imessage|sms|note)( message)? to <NAME> (saying|that says|that|:|to say)? <BODY>`
     - `send (a|an) <BODY-WORD> (text|message) to <NAME>`, e.g. "send a hello message to Arda" -> body "hello"
     - `(text|message|imessage) <NAME> (saying|that|:)? <BODY>`
     - `send <NAME> a (text|message) (saying|that)? <BODY>`
     - `tell <NAME> (that)? <BODY>`
     - each form without a body -> `body=None`
   - Strip fillers and handle self-corrections in NAME: "Orda, Arda", "Orda I mean Arda", "Orda no Arda",
     "Orda sorry Arda" -> the last name.
   - Pronouns or vague people as NAME (her, him, them, they, she, he, someone, somebody, a friend, my friend)
     -> ASK "Who should I text?" with a pending slot. Never search Contacts or Messages for a pronoun.
   - Hard rule: an utterance containing text/texting/message/imessage/sms, and not email/e-mail/mail/gmail,
     never reaches compose_email or draft_email, whether through the router, the planner skill line or
     slot fill. Route it to `comms.send_message`.
   - `body=None` -> say "What should the message to <Name> say?" and set a pending comms state (kind
     `body`). The next utterance becomes the body, unless it's cancel or a clearly different command
     (router p >= 0.8 for another skill).
   - Never type the body anywhere else.

2. **A new command while comms is waiting restarts the flow.** In `comms.answer`, when the pending state is
   `handle` or `choose`: if the utterance parses as a messaging request (parser above) or routes to
   send_message with p >= 0.8, drop the pending state and run the new request from scratch with its own
   to/body. Today the whole sentence becomes a name.

3. **Whole-name fuzzy answers.** In `resolve_answer`, after the current rules:
   - compare the answer with spaces and punctuation removed, casefolded, against each option's full name
     and first+last;
   - use `difflib.SequenceMatcher` ratio; accept the best if ratio >= 0.75 and it beats the second best by
     >= 0.10.
   Tests: "Ardaoke" -> Arda Hoke, "Arda okay" -> Arda Hoke, "Arda Didim" exact; ambiguous -> ask again.

4. **iMessage people first** (the user's request: search the people you actually text, then Contacts).
   - New RPC `messages_people {query, limit:5}` (section 6). Call it first. Rank its people above Contacts
     results.
   - If exactly one Messages person matches at the best name tier, use it without asking, even if Contacts
     has more namesakes.
   - Otherwise merge with `contacts_search` results, deduped by handle digits/email, and keep the existing
     ask logic.
   - If `messages_people` errors (unknown method on an old app, `messages_automation_denied`, or a timeout
     over 4 s), fall back to Contacts silently.
   - Trace `comms.resolve.source` (messages | contacts | both).

5. **Fuzzy fallback on zero matches.**
   - When both searches return nothing for a name, call `contacts_search {query, limit:5, fuzzy:true}`
     once.
   - If it returns candidates, ask "Did you mean Arda Hoke?" (one candidate) or "Arda Hoke or Arda Didim?"
     (several), with the pending `choose` state.
   - Only then ask for a number or email.

6. **Swift contract** (the lead's team implements it on the Mac; your code must call it exactly so):
   - `messages_people {query, limit}` -> `{people:[{name, handles:[{kind:"phone"|"email", value}], chat:true}], ms}`
     - people the user has Messages conversations with, matched by name;
     - errors `messages_automation_denied`, `messages_unavailable`.
   - `contacts_search {query, limit, fuzzy?:bool}` -> as today, plus a per-match `score` (0..1) when fuzzy.
   - `messages_compose {handle, body, name?}`: pass `name` = the resolved display name (contact or
     Messages person). Swift accepts it as an extra identifier in the recipient check. Never pass a name
     the user didn't confirm or that didn't come from a single best match.

7. Keep every existing safety property:
   - confirm before send, showing the resolved name;
   - no/timeout leaves a draft;
   - never a raw unresolved name;
   - planner failures are terminal (no retry of a send).

## Tests

- Every row in the evidence table as an end-to-end fake test, asserting the exact RPC sequence and bubbles.
- The parser on 40+ phrasings, including ASR-ish lowercase, no punctuation, fillers and "uh".
- Pronouns ask.
- The email/message channel boundary ("email arda saying hi" still goes to the email path).
- `messages_people` fallback paths.

Report in the PR body: what changed, test counts (`uv run --project ml python -m pytest ml/tests -q`,
`bench/tests`), and anything unsure. Don't merge; the lead reviews.
