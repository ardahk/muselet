# evals-safety digest (pass 103, 2026-10-26T03:41:01Z)

Counts: P0 2, P1 14, P2 15.

## Ranked open P0/P1
1. evals-safety-56 (P0) Enter-to-send confirm skipped when composer label contains search/find (sendgate.py:79-80).
2. evals-safety-50 (P0) Sealed HobbyLM D04-D06 utterances committed and tuned on.
3. evals-safety-59 (P1) Finance/advisor engines deleted on main; claims.md:221 and REPORT.md:296 still say "computed by code"; finance/advisor evals still pending.
4. evals-safety-57 (P1) Failed expects no longer stop batches, and expect is stripped before HandsKit (now on main).
5. evals-safety-58 (P1) Destructive-refusal regex blocks valid empty_trash requests.
6. evals-safety-61 (P1) LH-v1: 13/18 cases depend on an untracked fixture server.
7. evals-safety-54/48/49/51/46/43/25 (see findings.jsonl).

## Next moves
1. -56: skip only for real search fields; add Slack/Messages tests.
2. -59: re-enable finance/advisor evals graded against answer key; delete/rewrite claims.md:221 and REPORT.md:296.
3. -57: end batch on failed expect without counting it toward the limit; send expect to HandsKit.
4. -58: restrict refuse rule to files/folders/disks; exclude trash/bin.
5. -61: commit bench/fixtures/server.py before logging any LH-v1 result; fix wiki_taller (-62).
