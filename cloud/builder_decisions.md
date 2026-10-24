# Cloud builder: generalist System One decisions (research + data + Tinker iteration + cloud eval) — Muselet

Repo `ardahk/muselet`. Read `AGENTS.md` first, especially "Standing decisions from the user", "Decision API" and
"Never train on eval sets". Muselet's System 1 is Qwen3.5-4B (+ LoRA trained on Tinker) reading choice-token logits
after a prefilled `choice#` (one forward pass, no generation). The same model answers DeskMind/TypeSafe-style
`POST /v1/systemone` typed questions (`choice`, `noul`, `score`) through `bench/systemone/` (server/schema) and
`ml/src/brain/generic_decide.py` (`_decision`, `_choices`, `GenericRenderer`: the vendored tinker-cookbook
`DecisionRenderer` + our `AlphaChoiceRenderer`). If those files aren't on `main` yet, they are on branch `cloud/bench`.

## Why
Measured tonight on the M5 Pro with the official runners (same shim, same clock):

| model | JevBench public (231) | easy / original / hard | typed-decisions test (400 cases) | choice / noul / score |
|---|---|---|---|---|
| Muselet = base Qwen3.5-4B-4bit, zero-shot | 0.719 | 1.000 / 0.833 / 0.523 | 0.569 | 0.557 / 0.667 / 0.505 |
| DeskMind brain-4b G18b (8-bit) | 0.831 | 1.000 / 0.958 / 0.676 | 0.658 | 0.657 / 0.702 / 0.626 |

The gap is the JevBench hard split (temporal/numeric, hard judgement, multi-hop) and `score` questions. The user's
goal is to beat DeskMind on its own benchmarks, on this machine, without giving up System-1 speed.

## Research first (write `docs/decisions_research.md`, cite every claim with a URL)
1. DeskMind's recipe: `github.com/deskmind-ai/brain` `docs/training.md`, `docs/results.md`, and the HF blog
   `gxcsoccer/deskmind-local-decision-models`. Cover the data mix (G18b: 100,703 items), item types, the loss (KL to
   teacher plus CE), counterexamples against label shortcuts, LoRA settings, which JevBench tiers moved between G14
   and G18b and why, and their 13-gram plus option-set contamination check.
2. typed-decisions (`LocalLLaMA/typed-decisions`, README leaderboard) recipes for small models. Zero-shot: d3-mini 4B
   0.743, d1-3B. Fitted: Decider-4B (Qwen3.5-4B + LoRA) 0.8205, od1, pramana. From their model cards and
   discussions, record the data used, temperature calibration, and anything about `score` questions.
3. JevBench: the cloned repo is not in git; clone `github.com/fstandhartinger/jevbench`. Read its METHOD docs and
   datasets: what each tier tests, the scoring, the rules on training data and disclosure.
4. Public datasets usable as generic decision training data, license-compatible (Apache/MIT/CC-BY; CC-BY-NC allowed
   for the hackathon build only, tracked in `data/LICENSES.md`). Look for temporal/date reasoning, numeric
   comparison, multi-hop evidence, policy/compliance judgement, agent-step and form decisions.
End with explicit hypotheses: what data and format changes should move hard-split and score accuracy, by how much,
and why.

## Build
- **Zero-shot claim first.** The primary model must NOT train on typed-decisions (train or test), so its
  typed-decisions score is honestly zero-shot like DeskMind's. A second, "fitted on train" variant is optional and
  only if budget allows; label it as such.
- **Never train on JevBench public items or DeskMind/HobbyLM benchmark data.** Decontaminate every item against
  JevBench public (231 items), the typed-decisions test, `evals/route_v1.jsonl`, `evals/live_t1.jsonl` and
  `evals/external/utterances.jsonl`: word 13-gram overlap AND identical option sets. Report the counts; they must be 0.
- **Synthetic decisions** from frontier teachers (OpenAI / Anthropic keys are in the environment), in the System One
  schema (state + typed questions with criteria), across the competencies the research identifies.
  - Soft labels: the teacher's distribution (mean of several samples, or token logprobs where available).
  - Wherever the answer is verifiable (date arithmetic, numeric thresholds, counting, multi-hop lookups), compute the
    gold by code and reject teacher disagreements.
  - Target about 15–25k decisions, balanced over choice / noul / score, and over option counts 2–12.
- **Render** with exactly the shim's path (`_decision` plus `GenericRenderer`), so training tokens equal inference
  tokens. Add a parity test against `bench/systemone` renderings.
- **Training on Tinker**, multi-task with the route data so one adapter serves both.
  - Coordinate through the lead for cloud A's iteration-2 route datums (branch `cloud/data-pipeline`, private HF
    datasets under `jonsnov/`).
  - Fallback: continued training from cloud A's best route checkpoint, with ≥30% route replay.
  - Same soft-label loss as the route training.
  - Before every run, post the written hypotheses and a token/$ estimate. Over $25 per run waits for the lead's OK.
    The total Tinker cap is $150, shared with cloud A (≈$37 spent, ≈$32 committed). Keep every checkpoint.
- **Cloud eval, no Mac needed.**
  - Add a Tinker-sampler-backed Decider for `bench/systemone`: choice-token logprobs at the answer position.
  - Run JevBench public (official `jevbench.cli`) and typed-decisions test (`bench/typed_decisions.py`, its
    verbatim scorer) through it, plus `evals/route_v1.jsonl` (route top-1 and macro-F1 must not drop more than
    1 point vs cloud A's route-only model).
  - Fit temperature calibration on your own held-out synthetic dev split only.
  - Report per tier / per type accuracy plus KL / Brier / ECE, before vs after.

Branch `cloud/decisions` from `main`, one PR. Code under `training/decisions/`, `ml/src/brain/` (decider only),
`bench/systemone/` (Tinker backend only), `docs/`, tests under `ml/tests/` or `bench/tests/`. Data artifacts go to a
private HF dataset under `jonsnov/`, never into git. Report blockers rather than guessing. Reply after the research
with the hypotheses and the data plan (before spending more than $5 on generation), then again with results.
