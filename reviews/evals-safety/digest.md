# evals-safety digest — pass 37 (2026-10-24T16:47:08Z, main@cf53292)

Open: P0 0, P1 4, P2 9.

## Open P0/P1 (ranked)
1. **-34 (P1, new; cloud/comms 956d4ac):** every send_message now needs the HandsKit RPCs contacts_search, messages_compose and messages_send, which exist in no pushed app/ code. If comms merges alone, all sends fail ("Couldn't search your contacts"). This fails closed, and the confirm flow is correct.
2. **-25 (P1):** the first live run executed 27 of 43 cases (T1 19/22, T2 1/5). Skip reasons are not reported, and the /43 template remains.
3. **-11 (P1):** `done` has no harness goal check. There were 4 false_done in 27 live cases.
4. **-33 (P1):** main (with brain-7) and cloud/app-ui disagree on config_ack (app reads `ok`, brain never sends it). Merging conflicts in server.py.

## Next moves
1. Land the HandsKit contacts/messages RPCs together with cloud/comms, or keep a fallback (-34).
2. Publish per-case skip reasons for run 20261024T161427Z, and quote passed/executed (-25).
3. Triage the 4 false_done traces: each is a case where a harness goal check would have caught a false success (-11).
4. Settle one config_ack contract before app-ui merges (-33).
5. REPORT.md:122 and claims.md:66: add the 12/43 trace-graded caveat (-24).

## Checked, nothing material (pass 37)
- main cf53292: the brain-7 merge (reviewed in pass 36), REPORT.md, native-research, and three data briefs.
- data-pipeline f8b721a: gate_filter drops pool rows overlapping any frozen eval, on both raw and ASR-noised text.
- report-2: planner numbers now on the shipped prompt (holdout2 .667 shown), and speed marked as measured on the earlier config. Decisions API cap raised to $120 by the user (lead-reported); Tinker billed $64.89 of $150.
