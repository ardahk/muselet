
## Your lane: `evals-safety` — measurement integrity, finance answer keys, security
Files: `evals/*` (incl. `evals/route_v1.jsonl`, 128 hand-labeled router cases), any eval/benchmark harness
in `ml/` or `bench/`, everything on `cloud/fixtures-docs` (PR #1: finance fixtures + answer keys, docs
corpus scraper, Premiere UXP bridge `premiere/`), `cloud/session_b.md` (the fixture rules), plus a
repo-wide security sweep.
Look hardest at:
- `evals/route_v1.jsonl`: check every label against `skills/catalog.json` and the special options
  (MULTI_STEP, ASK, REFUSE, ANSWER). Report mislabels or ambiguous cases with the reason; these numbers are
  the measurement of record.
- Finance fixtures: independently recompute every answer key from the raw fixture files with your own
  code (category totals, duplicates, the ~$1,299 outlier, the refund, weekend charges, receipt matches incl.
  the transposed-digit mismatch and the unmatched receipt, over-budget categories). Compare with the
  committed keys; any disagreement is P0. Check the fixtures obey every rule in `cloud/session_b.md`.
- Harness honesty: success must be final-state verified, never model-claimed; latency must be measured
  end-to-end and per stage; no cherry-picking; baselines (HobbyLM, DeskMind) run on the same machine and
  task set.
- Security: secret-like strings anywhere in any branch or its history (report path + commit only, never
  the value); `.gitignore` coverage; Premiere bridge (localhost-only, no arbitrary code execution from
  untrusted input); script/shell confirmation policy and destructive-action gating in the brain; prompt
  injection from on-screen/web text reaching the planner as instructions.
