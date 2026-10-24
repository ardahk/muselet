# Lane: safety-2 — implement the W9 safety backlog

Brief of record: `cloud/handoff/W9_safety_backlog.md`. Continue from branch `cloud/w9-safety` @ `d5fe82b`: the
previous agent verified the backlog items and wrote `cloud/handoff/notes/w9-safety.md` on that branch (including a
test-environment gotcha), but fixed nothing yet. Also read the reviewer digests on `origin/review/evals-safety`,
`origin/review/brain` and `origin/review/hands` (`reviews/<lane>/digest.md`) for open safety findings.

## Do
- Fix the items in priority order (anything that lets an external/destructive action run without a confirm first:
  script-confirm bypasses, per-action confirms, voice-confirm negation such as "no, don't send it", `done` without
  verification). Each fix gets a regression test.
- Python in `ml/src/brain` with tests; Swift (HandsKit) changes in separate small commits marked uncompiled.
- Don't weaken existing gates (permission-prompt gate, contacts-first messaging, sign-in field guard, relative-path
  refusal, document inventory).
- Open a PR early from your branch and add fixes as you go; the PR body has a table: item, status
  (fixed+tested / deferred + why), test name.

No Tinker. API cap: $5 per provider.
