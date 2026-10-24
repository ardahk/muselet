# evals-safety digest — pass 38 (2026-10-24T19:05:18Z, main@e56582b)

Open: P0 0, P1 3, P2 9. Resolved this pass: -33.

## Open P0/P1 (ranked)
1. **-34 (P1; cloud/comms c94a407):** send_message needs HandsKit RPCs contacts_search, messages_compose and messages_send, which exist in no pushed app/ code. If comms merges alone, every send fails. This fails closed.
2. **-25 (P1):** the live run executed 27 of 43 cases. The document guard and the executed-only denominator are unchanged. bench-fix (unmerged) adds per-case skip reasons.
3. **-11 (P1):** `done` has no harness goal check (4 false_done in 27 live cases).

## Next moves
1. Land the HandsKit contacts/messages RPCs with cloud/comms, or keep a fallback (-34).
2. Merge bench-fix's skip reasons, publish them for run 20261024T161427Z, and quote passed/executed (-25).
3. Triage the 4 false_done traces (-11).
4. REPORT.md:122 and claims.md:66: add the 12/43 trace-graded caveat (-24).

## Checked, nothing material (pass 38)
- app-ui ae9ce5e: now parses brain-7's config_ack and merges into main cleanly (-33 resolved).
- data-route 42835ce: the 4-rule overlap gate over route_v1/live_t1/route_v2/HobbyLM dropped all 156 hits before export.
- data-planner ee8ae33: 260 scenarios, split 50/50 per category, and the validator enforces that no goal is shared across splits or with v1.
- decisions 694c198: LR pilot checkpoint records only.
