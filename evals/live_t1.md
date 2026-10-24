# Live suite `live_t1.jsonl` (measurement of record for on-Mac capability)

Each line is one task run through the real stack (app or `hands serve --utterance` -> brain -> HandsKit) on this
Mac and graded by final state, never by what the agent said. Tiers: `T1` = one native skill or routing decision,
`T2` = multi-step (planner or brain tool).

Fields:
- `id`, `tier`, `category`, `utterance`.
- `precondition` (optional): checks that must hold before the case runs, else the case is SKIPPED (protects the
  user's own documents/apps, e.g. "TextEdit is not running").
- `restore` (optional): `[{"get": <applescript>, "set": <applescript with {value}>}]`; the runner reads each value
  before the case and writes it back afterwards (volume, appearance, clipboard).
- `setup`, `teardown`: lists of steps `{"applescript": ...}` or `{"shell": ...}` (`{{sandbox}}` = `~/MuseletSandbox`,
  created by the runner and removed at the end). Teardown only touches what the case created.
- `confirm_reply`: `true`/`false`/`null` - how the runner answers a `confirm` frame (null = fail the case if asked).
- `expect_outcome`: `ok` | `awaiting_user` | `cancelled` | `refused` (router label REFUSE or planner `refuse`).
- `check`: list of predicates, all must pass: `{"applescript"|"shell": ..., "equals"|"contains"|"int_between"|"not_contains": ...}`
  or `{"trace_skill": {"name": ..., "args": {...}}}` (the skill RPC was sent with these args - used only where no
  state can be read back) or `{"trace_say": {"contains": ...}}` (the bubble text, for ANSWER-style tasks). Template vars resolved at run time: `{{tomorrow_ymd}}`, `{{next_friday_ymd}}` as
  `YYYY-M-D` (no zero padding).
- `forbid`: predicates that must NOT become true (side effects), plus `{"trace_rpc": {"method", "name"}}`.
- `manual: true`: needs the user present (network, Bluetooth, lock screen); never run unattended.
- `timeout_s`, `online` (needs internet), `pending` (waiting on a feature; run but report separately).
Checks and setup run through HandsKit (`act` script RPC from the runner), which holds the TCC permissions.
Metrics: strict pass rate per tier, pass^3, false-done (agent said done/success but checks fail), time from
utterance end to first action and to verified completion (p50/p95), confirms asked.
Every live failure seen in use is added here as a regression case (`id` prefix `reg-`).
Training data must be deduped against these utterances.
