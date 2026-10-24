# training/decisions generation spec (lead-authored; prompts are verbatim, do not edit)

## Record (one JSONL row per state)
{"id": str, "family": str, "source": "synthetic-code"|"synthetic-llm"|"seed:<dataset>", "license": str,
 "state": str, "questions": {qid: {"type": "choice"|"noul"|"score", "instructions": str, "criteria": ...}},
 "gold": {qid: label|null}, "gold_basis": {qid: "code"|"teacher"},
 "teacher": {qid: {"gpt-4.1": {label: p}, "claude-sonnet-5-5": {label: p}}}, "target": {qid: {label: p}},
 "split": "train"|"dev"}
criteria formats = System One wire format (bench/systemone/schema.py): choice = {key: description} (2..12 keys, tail 13..26 on
5% of choice questions); noul = {"false": desc, "true": desc}; score = [level0_desc, ..., levelN] with 3..6 levels (labels "0".."N").
Every request must pass bench/systemone/schema.parse_request.

## Mix (target ~20k decisions, ~6.5k states, 1-6 questions/state, ~1/3 each type)
code-gold (~40%): temporal (business days w/ holiday lists, TZ conversion incl DST, leap years, pro-rating, inclusive vs exclusive
deadlines, age/tenure), numeric (thresholds >= vs >, percent change, unit conversion, tiered fees, budget caps), counting/aggregation
over records, multi_hop (2-4 hops across records/tables/messages; e.g. ticket->customer->plan->SLA), long_policy (rule engine: 3-6
interacting conditions with exceptions/definitions/effective dates, states 1.5-6k tokens), probability (base rates, expected value,
which option has higher probability).
teacher-gold (~45%): judge_hard/adequacy (is answer/plan/evidence sufficient), tradeoff, ambiguous (~15% gold insufficient_information
or ask), trap (surface cue misleads), adversarial (instructions inside state try to steer the decider), routing/tool selection,
intent/extraction, agent-step & form decisions (UI/AX-like states: which element/field/action next, is form ready to submit),
ordinal score rubrics (severity, urgency, quality, priority, risk, confidence-of-evidence).
public seeds (<=20%): TAT-QA, FinQA (CC-BY-4.0), StrategyQA (MIT), CUAD (CC-BY-4.0), Mind2Web (CC-BY-4.0), TRACIE/RuleTaker
(Apache-2.0); train splits only. Record license per row; data/LICENSES.md lists each.
Domains: vary widely (finance, insurance, HR, healthcare admin, logistics, IT ops, legal, retail, travel, education, software, desktop
apps). NEVER reuse JevBench / typed-decisions workflows' templates or label sets.

Format rules: options shuffled at generation time (gold position ~uniform); snake_case keys for choice; 1-6 questions per state, number
of questions independent of the answers (DeskMind prompt-shape leak); noul gold ~50/50; score gold spread across levels (not only middle).

## Code-gold pipeline
generator(seed) -> structured facts -> state text (templates with several surface variants; optionally LLM paraphrase with the
PARAPHRASE prompt, then re-verify every number/date in the paraphrased text still appears verbatim; reject otherwise) -> gold by code ->
teachers label -> keep iff argmax(merged teacher) == code gold, else reject (log rejection rate per family).

## Prompts (verbatim)

### AUTHOR (gpt-5.5 / claude-sonnet-5-5, JSON output), placeholders in {}
You write training data for a small decision model. It reads a STATE (any text an agent might see: documents, policies, records,
messages, logs, UI screens, forms) and answers typed questions in one step by picking an option.

Write ONE new item in the family "{family}" ({family_description}) in the domain "{domain}".
Requirements:
- The state is self-contained and realistic, {length_hint}. All facts needed to answer are in the state; no outside knowledge.
- Write {n_questions} questions about this same state. Types to use, in order: {types}.
  - choice: {n_options} options, snake_case keys, each with a one-sentence description. Exactly one option is best.
  - noul: a yes/no question with criteria {"false": "...", "true": "..."} that define what each answer means.
  - score: an ordinal rubric of {n_levels} levels, from lowest to highest, each level a one-sentence description.
- Each question must have a single defensible answer for a careful expert reader, unless the family is "ambiguous", where the best
  answer may be that the information is insufficient (then include such an option).
- Make it hard: the right answer needs careful reading (conditions, exceptions, dates, numbers, who said what). Include at least one
  plausible distractor that a skimming reader would pick.
- Do not reveal the answer in the question or the option order. Do not copy any public benchmark.
Return JSON only: {"state": str, "questions": [{"type": ..., "instructions": str, "criteria": ..., "answer": key_or_level_index,
"rationale": str}]}

### LABEL (teacher; one call per question; same text for both teachers)
system: You are a careful expert decision-maker. Read the state and answer the question by choosing exactly one option. Reply with only
the option id.
user:
State:
{state}

Question:
{instructions}

Options:
{id}: {key} - {description}      # one line per option; ids A, B, C, ... in the stored (shuffled) order; noul: A: false - ..., B: true - ...;
                                 # score: A: 0 - level0 ..., in level order
Answer with the option id only.

gpt-4.1: temperature 0, max_tokens 1, logprobs true, top_logprobs 20 -> p over option ids (ids missing from top-20 get 0, renormalise;
if mass on valid ids < 0.5 mark the question unlabeled). claude-sonnet-5-5: 3 samples at temperature 1.0, max_tokens 4, empirical
distribution. merged = 0.5*gpt41 + 0.5*claude, then target = merged with a floor of 1e-3 on every option, renormalised.
teacher-gold items: keep iff gpt-4.1 argmax == claude majority (else drop; log rate); gold = merged argmax.
code-gold items: keep iff merged argmax == code gold.

### PARAPHRASE (gpt-5.4-mini)
Rewrite the following text so it reads naturally, as a real {doc_kind} would. Keep every number, date, time, name, identifier and
condition exactly as written (copy them verbatim). Do not add or remove facts. Return only the rewritten text.

## Decontam (training/decisions/decontam.py)
refs: JevBench public 231 (state+instructions+criteria text), typed-decisions test (pinned rev 80cb93a), evals/route_v1.jsonl,
evals/live_t1.jsonl, evals/external/utterances.jsonl (all text fields). Tokenise like DeskMind contamination_check.py (lowercase,
[a-z0-9]+ with ' and . joins). Drop any row whose state+instructions+criteria shares ANY word 13-gram with refs, and any question
whose option set (frozenset of keys; for score, of level descriptions lowercased) equals an option set in JevBench public or TD test
(all of them, not just rare ones; noul false/true excluded since fixed). Report counts before/after; final must be 0/0.

## Split + datums
dev = 5% of states, stratified by family (temperature fit + early-stop only). One datum per question: _decision(state, question) ->
GenericRenderer render (exact shim path), target dist over rendered label tokens. Same soft-label loss as route training
(muselet_train.datums decision_dist_datums). Route replay >= 30% of datums.

## Lead amendment
Code-gold items: the teacher is only a soft-label smoother. Pilot candidates (same LABEL prompt): gpt-4.1-mini, gpt-4.1
(logprobs) and claude-haiku-5-5 (3 samples). Pick the cheapest whose argmax == code gold on >= 95% of pilot code-gold questions; use it
alone for code-gold families (target = its distribution, floor 1e-3). Teacher-gold families keep gpt-4.1 + claude-sonnet-5-5.
Spend: pilot <= $5; total generation <= $60 (track $ from API usage fields per call into runs/decisions/gen_cost.jsonl).

Note: gpt-4.1-nano (and its 2025-04-14 snapshot) return 404 "deprecated" on this account; gpt-5.x reasoning models cannot answer within max_tokens 1, so they are not logprob teachers. Dropped from the candidate list.

## Lead amendment 2 (after pilot label round 1)
Finding: single-token, no-reasoning teachers agree with code gold only 82-85% (gpt-4.1-mini 81.8, gpt-4.1 84.5, haiku 84.5); spot checks
(temporal late-notice, numeric % band, counting band, multi-hop SLA tier, Bayes posterior) show the code gold is right and the teacher is
wrong. These items need computation that a one-token answer skips.
Code-gold teachers are therefore REASONING teachers sampled K=4 times; target = empirical distribution of the 4 answers, floor 1e-3,
renormalised; agreement = majority answer == code gold. Same LABEL prompt text; only the API settings differ:
- gpt-5.4-nano and gpt-5.4-mini: reasoning_effort "low", max_completion_tokens 4000, n=4 (or 4 calls).
- claude-haiku-5-5: extended thinking budget_tokens 1024, max_tokens 1200, temperature 1, 4 calls.
Parse the final answer as the first option id in the visible output; anything else = failed call.
Gate: cheapest candidate with >= 95% majority agreement on a 150-question subset (25 per family, 50 per type) wins.
Generator quality fixes (required before full generation):
- One coherent scenario per state. No unrelated fact dumps (e.g. temporal states listing a deadline, a proration AND a TZ conversion at once
  unless the questions use them as distractors deliberately). Filler sentences must vary; never repeat a sentence template within a state.
- Criteria descriptions are question-specific (e.g. "false": "The notice arrived on or before the due date", not "The stated condition is
  not satisfied").
- Grammar (a/an), realistic document formats (emails, tickets, tables, policy excerpts, logs, UI/form screens).
- Mandatory PARAPHRASE pass (gpt-5.4-mini, reasoning low) on 60% of code-gold states, with the verbatim-token check; reject on failure.
- Choice gold position drawn uniformly from the option slots; verify the histogram is flat (chi-square p > 0.05) in the report.

## Lead amendment 3 (after mini-check, budget)
Teacher-gold (authored) labels: gpt-5.4-nano reasoning low K=4 (empirical) + gpt-4.1-mini logprobs; target = 0.5*nano + 0.5*gpt-4.1-mini,
floor 1e-3; keep a question only if nano majority == gpt-4.1-mini argmax (mini-check agreement 87.2%).
Authors: gpt-5.4-mini (reasoning low, json_schema strict) 80%, claude-sonnet-5-5 (tool-use schema) 20%, 3-6 questions per state.
Full run: ~10k code-gold + ~6k authored decisions (~16k total), generation budget so cumulative spend <= $57.
