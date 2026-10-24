# Cloud builder: planner-retrieval, 1-2 similar solved examples per request — Muselet (Python)

Repo `ardahk/muselet`. Read `AGENTS.md` (planner config, offline planner bench, "never tune on holdouts") and
`evals/planner_v2_REPORT.md`. Branch `cloud/planner-retrieval` from main, one PR. Python only. No edits to
`prompts/planner_system.md` or `prompts/planner_fewshot.md`, and no edits to the v1/v2 scenario files.

## Hypothesis (lead)
The tuned 4B planner is .88 on tune but .643 / .667 on the two holdouts. Its static few-shot block covers a few
patterns. Literature on small models: kNN or BM25-selected in-context examples beat fixed examples, especially on
format-sensitive tasks (Liu et al. 2021 "What Makes Good In-Context Examples for GPT-3"; Rubin et al. 2022). We
expect +5 to +10 points on holdouts from 1–2 retrieved, validated examples. Each example costs about 150–400
prefill tokens after the cached static prefix, so roughly 0.1–0.2 s.

## Build
1. **The bank.** `ml/src/brain/plan_bank.py` loads demos from a JSONL with fields
   `{goal, app, category, obs_header, batch:[lines]}`.
   - v1 source: only `split == "v2-tune"` rows of `evals/planner_scenarios_v2.jsonl`, using their first
     `gold` reply. These are validator-checked.
   - Never use v2-holdout, v1 tune/holdout/holdout2, the live suite, HobbyLM or DeskMind, and enforce that
     in code with an id/goal denylist test.
   - The data-planner builder will later ship `jonsnov/muselet-planner-demos-v1`. Support loading that too,
     behind a flag.
2. **Retrieval.**
   - BM25 over goal tokens + app name + observation-header tokens. Implement it in pure Python; no new deps
     unless already in `ml/pyproject.toml`.
   - Return the top k (k ∈ {0, 1, 2}).
   - Skip demos whose goal shares a 13-gram or is within edit distance 1 of the current goal. This prevents
     test leakage when someone evaluates on bank-adjacent data.
3. **Prompt placement.**
   - Insert the examples after the cached static prefix, before the dynamic state, as a short block in the
     exact format the planner already uses for few-shot examples (read `planner.py` and
     `prompts/planner_fewshot.md` for the format).
   - The static prefix cache must keep working: dynamic examples go after the snapshot point.
   - Flag: `Planner(..., retrieval_k=0)` default 0 (off), with CLI `--planner-retrieval-k` in `brain serve`
     and the offline bench `evals/planner_offline.py --retrieval-k`. Also add it to `evals/planner_v2_run.py`.
4. **Offline evaluation plan.** Write the exact commands into the PR body; the lead runs them on the Mac.
   - Configs k = 0, 1, 2 × sets v1-tune, v1-holdout, v1-holdout2 and v2-holdout.
   - Report the pass rate, mean prompt tokens and TTFT.
   - Decision rule, pre-registered: ship k > 0 only if mean holdout pass (v1-holdout, v1-holdout2,
     v2-holdout) improves by ≥ 3 points over k = 0, with no single set dropping by more than 1 scenario, and
     TTFT +≤ 150 ms.

## Tests
- Bank loading and the denylist.
- BM25 ranking on toy data.
- Leak filter.
- The prompt layout: the static prefix is byte-identical with and without retrieval; examples appear after it.
- Flag plumbing.

Report in the PR body: files changed, test counts, the exact Mac commands, and the pre-registered decision rule.
