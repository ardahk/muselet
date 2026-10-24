# Common rules for every Muselet cloud builder (new org, from Sat Oct 24 2026 14:30 PDT)

Repo `ardahk/muselet`. You work in a **new** Devin org: the old org's agents are gone. Their state lives only in
GitHub branches/PRs (`## Handoff` sections, `HANDOFF.md` / `cloud/handoff/notes/*.md`), Hugging Face and Tinker.
Read `AGENTS.md` first, then your lane brief below, then the old handoff notes it points to.

- **Deadline:** Cal Hacks submission Sun Oct 25 09:00 PDT. Freeze Sun 06:00 PDT (after that: bug fixes with tests
  only). Land work in small, reviewable PRs early rather than one big PR late.
- **Tinker is nearly exhausted:** the console showed $136.22 of the $150 hard cap at 14:30 PDT Sat, and the API
  (`python3 tools/tinker_spend.py`) lags by hours. The user allows using the full $150; hard stop at $148.
  **No new Tinker training run unless your brief explicitly approves one** (only the planner-lora lane has one).
  Sampling only where your brief allows it, within the lane cap stated there. Estimate every sampling job's cost before running it
  (uncached prefill is about $0.33 per million tokens), log it in your PR, and abort if `tools/tinker_spend.py`
  reports month-to-date ≥ $140. Prefer exporting weights and letting the lead evaluate on the Mac (free).
- **OpenAI / Anthropic:** about $130 of the $200-per-provider budget is already used across lanes; your brief
  states your lane's cap.
- **Never train on or tune on eval sets** (list in `AGENTS.md`, plus `evals/route_v1*`, `evals/route_v2.jsonl`,
  `evals/live_t1.jsonl`, planner holdouts, `evals/planner_scenarios_v2` v2-holdout, `evals/memory_followups*` holdout).
- **Swift you write is uncompiled** (no macOS here). Keep Swift changes in separate commits, say so in the PR,
  and keep them small; the lead compiles and tests them on the Mac before merging.
- Python: `uv run --project ml ...`; run the relevant tests (`uv run --project ml pytest ml/tests -q`, and
  `bench/tests` when you touch `bench/`). Follow existing code patterns, keep code compact, pin dependencies.
- **Commit and push to your branch at least hourly.** Keep a `## Handoff` section at the top of your PR body
  (state, next exact steps, artifacts with HF revisions / Tinker paths, spend, open questions), so another agent
  can resume if you stop.
- Don't merge your own PR; the lead reviews and merges. If blocked, write the question in the PR body and continue
  with the safest reasonable assumption.
- No secrets in code, logs or PR text. Keys come from environment variables only.
