# evals-safety digest — pass 40 (2026-10-24T20:06:41Z, main@7065dd3)

Open: P0 0, P1 3, P2 9.

## Open P0/P1 (ranked)
1. **-34 (P1, now on main):** comms is merged (6885b7c), so every send_message calls contacts_search, which no app code on main handles. Messaging fails closed. wip/local has Contacts.swift and MessagesCompose.swift, but RPC.swift does not route the three methods.
2. **-25 (P1):** skips are still left out of the live denominator. The Finder and document preconditions are unchanged.
3. **-11 (P1):** `done` has no harness goal check.

## Next moves
1. Wire contacts_search, messages_compose and messages_send into RPC.swift handle(method:) and push before any messaging demo or live run (-34).
2. Quote live numbers as passed/executed with skip_reason counts (-25).
3. Triage the 4 false_done traces (-11).
4. Add the trace-graded caveat (11/43) to REPORT.md and claims.md (-24).
