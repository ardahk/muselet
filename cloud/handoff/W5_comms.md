# W5: Messaging + email that understands people (Python + the Swift contract)

Repo `ardahk/muselet`. Read `docs/HANDOFF.md` §8 (messaging safety), the `ml/src/brain/comms.py` docstring, and
`cloud/builder_comms2.md`. That builder brief is the full spec for the Python side, including the evidence
table from the user's live attempts.

## State
- **Merged:**
  - contacts-first `send_message` (Python `brain.comms`);
  - HandsKit RPCs `contacts_search`, `messages_compose`, `messages_send` (Swift, `Contacts.swift`,
    `MessagesCompose.swift`);
  - the recipient check scoped to the window title + AXToolbar header + To field;
  - `draft_email` (Mail / Gmail; never sends without a confirm).
- **In flight:** `cloud/comms-2` (Python), which adds:
  - a deterministic messaging parser before the router;
  - pronoun → ask;
  - a new command restarts a pending flow;
  - whole-name fuzzy answers;
  - iMessage-people-first resolution;
  - a fuzzy fallback;
  - passing `name` to compose.

## Swift contract to implement on the Mac (if comms-2 is merged first, its PR documents the same contract)
- `messages_people {query, limit:5}` -> `{people:[{name, handles:[{kind:"phone"|"email", value}], chat:true}], ms}`
  - Source: Messages AppleScript `participants` of `chats`. Muselet already has Automation for Messages.
  - Match by name the same way `contacts_search` does, in recency order if available.
  - Errors: `messages_automation_denied`, `messages_unavailable`.
  - Cache for 30 s.
- `contacts_search {query, limit, fuzzy?:bool}`. With `fuzzy:true`: enumerate contact names (given, family,
  nickname, full), score each by normalized similarity, and return the top `limit` with `score` ≥ 0.75.
- `messages_compose {handle, body, name?}`:
  - accept `name` as an extra identifier in `recipientMatches`: a case-insensitive contains in the title, header
    and To texts;
  - **poll ≤ 2 s** for the Messages front window and compose field after `imessage:` opens. Today the first call
    races and returns `no_text_target`;
  - include `contact_name_lookup` (string or null) in error results for diagnosis.

## Safety invariants (must hold in every change)
- Never message a raw unresolved name.
- Confirm before send, showing the resolved name.
- No reply or a timeout leaves a draft.
- Only text from the title/header/To field verifies a conversation.
- Compose never posts Return. `messages_send` re-checks: frontmost, same window, unchanged draft.

## Live test (Mac, with the user present)
"send a message to Arda saying hello", "text Caleb that I'm running late", "send a text to Monica" → (asks for the
body) → "say hello", "send her a quick text" → asks who. Gmail: "open gmail and draft an email to my coworkers
saying hello" (in Zen, signed in). Mail reply: open an email in Mail → "reply saying thanks, I'll be there".
