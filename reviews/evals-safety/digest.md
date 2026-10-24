# evals-safety digest — pass 39 (2026-10-24T19:20:41Z, main@fb2cfd0)

Open: P0 0, P1 3, P2 9.

## Open P0/P1 (ranked)
1. **-34 (P1; cloud/comms c94a407):** send_message needs HandsKit contacts_search/messages_compose/messages_send, which are absent from all pushed app/ code. This fails closed.
2. **-25 (P1):** per-case skip reasons are now on main (bench-fix). Finder cases now also skip when any user Finder window is open, and skips are still left out of the denominator.
3. **-11 (P1):** `done` has no harness goal check (4 false_done in 27 live cases).

## Next moves
1. Land the HandsKit contacts/messages RPCs with comms, or keep a fallback (-34).
2. Quote every live number as passed/executed with the skip_reason histogram, and close Finder and document windows before runs (-25).
3. Triage the 4 false_done traces (-11).
4. Add the trace-graded caveat (now 11/43) to REPORT.md:122 and claims.md:66 (-24).
