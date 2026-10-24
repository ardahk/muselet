# W3: Clean, high-quality data (user priority: "more clean high quality data = better models")

Repo `ardahk/muselet`. Read `docs/HANDOFF.md` §1 (budgets, never train on eval sets) and the reports below. API budget:
up to $200 per provider in total. About $114 is used so far; report spend as you go. No Tinker runs from data lanes.

## Lanes and state
1. **Route/ARGS (data-route, done):** `training/data_route/REPORT.md`.
   - Audit of it2b: 7.7% route noise, 15.7% ARGS noise. The 10 weakest labels were re-judged across the full
     pool.
   - 1,378 new judged rows.
   - Output `jonsnov/muselet-route-datums-it3cand` @ `84595279`. Residue and next groups: PR #31
     `training/data_route/HANDOFF.md`.
   - **Next:** after W1 reports it3's per-label route_v2 errors, generate targeted minimal pairs for the 5 worst
     labels. Use the same two-judge + adjudicator gate and the same decontamination; keep the val split.
2. **Decisions code-gold (data-decisions, running):** branch `cloud/data-decisions`.
   - Programmatic generators with code-computed gold: counting, multi-hop table lookups, long policies via a
     rule engine, business-day/time-zone math, thresholds, Bayes, trap questions.
   - Target: diversity over volume (new formats, rule engines, trap types), 2,500+ states.
   - Ship as a new version of `jonsnov/muselet-decisions-v1` (or `-v2`) with the SPEC soft labels and the same
     decontamination (JevBench, typed-decisions test, route_v1/v2, live_t1, HobbyLM, DeskMind).
   - **Next:** finish, post per-family counts, and hand the dataset id to W2.
3. **Planner demos (data-planner, running step 2):** benchmark v2 is merged: `evals/planner_scenarios_v2.jsonl`,
   260 scenarios across 10 categories, 50/50 tune/holdout; report `evals/planner_v2_REPORT.md`.
   - Step 2 (approved, ≤ $90) is about 1,500 validated teacher demos from v2-tune plus new builder states,
     weighted to the live weak spots:
     - Finder file work;
     - "...and open it" follow-ups;
     - permission prompts → ask;
     - sign-in walls → ask;
     - web answers → `done "<answer>"`;
     - writing into the focused body;
     - Calculator / Clock / System Settings.
   - Keep a demo only if both teachers pass the state's grader.
   - Render with the runtime planner prompt **without** the few-shot block.
   - Output `jonsnov/muselet-planner-demos-v1`, plus a retrieval bank of demos ≤ 400 tokens each.
   - **Never** use v2-holdout, v1 tune/holdout/holdout2, live_t1, HobbyLM or DeskMind.

## Quality bar for any new data
- Every row passes: a context-consistency check, the code coercions (`ml/src/brain/argfix.py`), and grounding
  (values must appear in or follow from the utterance).
- Two independent judges (one OpenAI, one Anthropic), blind to gold; disagreements go to an adjudicator.
- Decontamination: normalized exact match, a shared 13-gram, token edit ≤ 1 for short items, and CJK characters
  count as one token each. It must report **0** hits.
- Every change is one line in a changes log; there's a provenance map per row.
