# evals-safety digest (pass 98, 2026-10-25T12:46:21Z)

Counts: P0 2, P1 14, P2 13.

## Ranked open P0/P1
1. evals-safety-56 (P0) Enter-to-send confirm skipped when composer label contains search/find (sendgate.py:79-80).
2. evals-safety-50 (P0) Sealed HobbyLM D04-D06 utterances committed and tuned on.
3. evals-safety-59 (P1) Finance/advisor engines deleted (wip); claims.md still says "computed by code"; finance/advisor evals pending.
4. evals-safety-57 (P1) Failed expects no longer stop batches in progress/agentic tasks.
5. evals-safety-58 (P1) Destructive-refusal regex blocks valid empty_trash requests.
6. evals-safety-60 (P1) AXLoaded `wait` short-circuit + dead repoll break / 15 s cap.
7. evals-safety-54/48/49/51/46/43/25 (see findings.jsonl).

## Next moves
1. -56: skip only for real search fields; add Slack/Messages tests.
2. -60: only short-circuit `wait` after navigation; return web_loaded from verify.
3. -59: re-enable finance/advisor evals graded against answer key; fix claims.md.
4. -57: end batch on failed expect without counting it to the limit.
5. -58: restrict refuse rule to files/folders/disks; exclude trash/bin.
