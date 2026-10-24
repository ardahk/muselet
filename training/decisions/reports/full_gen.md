# Full decision generation

- Seed: `20261027`.
- Cumulative generation spend: **$52.890833 / $57.00** (this run $46.401581; OpenAI $32.693101; Anthropic $13.708480).
- Authored generation guard: stop near 6,500 decisions or $47.00 cumulative spend, whichever comes first.
- Generated code-gold decisions/states: 10002 / 2225.
- Generated authored decisions/states: 6537 / 1455.
- Retained after labels and decontamination: 6754 decisions / 1748 states.
- Family counts: `{"adversarial": 133, "agent_step": 248, "ambiguous": 135, "intent_extraction": 125, "judge_hard": 133, "numeric": 1, "ordinal_rubric": 287, "probability": 172, "routing": 128, "temporal": 128, "tradeoff": 126, "trap": 132}`.
- Retained decisions by code/authored family: `{"adversarial": 500, "agent_step": 962, "ambiguous": 514, "intent_extraction": 483, "judge_hard": 475, "numeric": 1, "ordinal_rubric": 1058, "probability": 787, "routing": 499, "temporal": 525, "tradeoff": 422, "trap": 528}`.
- Retained authored-family counts: `{"adversarial": 133, "agent_step": 248, "ambiguous": 135, "intent_extraction": 125, "judge_hard": 133, "ordinal_rubric": 287, "routing": 128, "tradeoff": 126, "trap": 132}`.
- Source counts: `{"authored": 1447, "code": 301}`.
- Generated questions/state: code 4.50; authored 4.49.
- Author states by model: `{"claude-sonnet-5-5": 291, "gpt-5.4-mini": 1164}`; retained states: `{"claude-sonnet-5-5": 288, "gpt-5.4-mini": 1159}`.
- Author retention and authoring+label cost by model: `{"claude-sonnet-5-5": {"authoring_and_label_cost_usd": 16.036095050000025, "generated_decisions": 1284, "generated_states": 291, "retained_decisions": 1036, "retained_states": 288, "retention": 0.8068535825545171, "usd_per_retained_decision": 0.01547885622586875}, "gpt-5.4-mini": {"authoring_and_label_cost_usd": 18.480509950000016, "generated_decisions": 5253, "generated_states": 1164, "retained_decisions": 4405, "retained_states": 1159, "retention": 0.8385684370835713, "usd_per_retained_decision": 0.004195348456299663}}`.
- Code paraphrases: 1127/2225 (50.7%); rejections: 165.

## Spend by API role

```json
{
  "paraphrase": 3.093381749999998,
  "teacher:gpt-5.4-nano": 16.03521130000001,
  "author": 25.02815874999999,
  "teacher:gpt-4.1-mini": 2.2448287999999947
}
```

## Question and option histograms

- Types: `{"choice": 2668, "noul": 2478, "score": 1608}`.
- Option counts: `{"10": 232, "11": 224, "12": 225, "2": 248, "25": 2, "26": 106, "3": 255, "4": 200, "5": 241, "6": 220, "7": 198, "8": 263, "9": 254}`.
- Choice gold positions: `{"0": 514, "1": 488, "10": 37, "11": 24, "12": 3, "13": 4, "14": 7, "15": 5, "16": 5, "17": 3, "18": 4, "19": 2, "2": 385, "20": 8, "21": 1, "23": 2, "24": 5, "25": 5, "3": 294, "4": 232, "5": 185, "6": 143, "7": 131, "8": 109, "9": 72}`.
- Gold-position quartiles: observed `[886, 588, 751, 443]`, expected `[851.76, 587.31, 775.26, 453.67]` under uniform within-question position; χ²=2.3870, df=3, p=0.49606.
- Noul true/false: `{"false": 1634, "true": 844}`.
- Score-level histogram: `{"0": 225, "1": 314, "2": 603, "3": 366, "4": 97, "5": 3}`.
- Mean max-probability / entropy nats by teacher: `{"gpt-4.1-mini": {"decisions": 5441, "mean_entropy_nats": 0.02299392925424134, "mean_max_probability": 0.9907030295410737}, "gpt-5.4-nano": {"decisions": 6754, "mean_entropy_nats": 0.05736470162200329, "mean_max_probability": 0.9837452371323007}}`.
- Author generation cost by model: `{"claude-sonnet-5-5": 13.70848000000001, "gpt-5.4-mini": 11.319678749999996}`.
- API spend per unique decision by role: `{"author": {"cost_usd": 25.02815874999999, "decisions": 1505, "usd_per_decision": 0.01663000581395348}, "paraphrase": {"cost_usd": 3.093381749999998, "decisions": 1292, "usd_per_decision": 0.0023942583204334352}, "teacher:gpt-4.1-mini": {"cost_usd": 2.2448287999999947, "decisions": 6537, "usd_per_decision": 0.0003434035184335314}, "teacher:gpt-5.4-nano": {"cost_usd": 16.03521130000001, "decisions": 16539, "usd_per_decision": 0.0009695393494165312}}`.

## Render and cost projections

- Mean rendered input tokens/Datum: 840.4.
- p95 rendered input tokens/Datum: 1425.
- 20k decision Tinker projection at $0.73/M train tokens: $12.2843 (using mean input tokens + one target token).
- 20k code-teacher generation projection using `gpt-5.4-nano`: $19.3908, from actual selected-teacher API usage per labeled code decision.
- Computed-answer leak audit: PASS; 2225 code states checked, 0 findings.
- Leak findings: `[]`.
- Code-gold nano agreement by family/type: `{"counting/choice": {"agreement": 0.9936305732484076, "correct": 624, "failed_or_no_majority": 10, "valid_majorities": 628}, "counting/noul": {"agreement": 1.0, "correct": 551, "failed_or_no_majority": 2, "valid_majorities": 551}, "counting/score": {"agreement": 0.9934065934065934, "correct": 452, "failed_or_no_majority": 9, "valid_majorities": 455}, "long_policy/choice": {"agreement": 1.0, "correct": 652, "failed_or_no_majority": 0, "valid_majorities": 652}, "long_policy/noul": {"agreement": 1.0, "correct": 553, "failed_or_no_majority": 0, "valid_majorities": 553}, "long_policy/score": {"agreement": 1.0, "correct": 459, "failed_or_no_majority": 0, "valid_majorities": 459}, "multi_hop/choice": {"agreement": 0.9535603715170279, "correct": 616, "failed_or_no_majority": 5, "valid_majorities": 646}, "multi_hop/noul": {"agreement": 1.0, "correct": 551, "failed_or_no_majority": 1, "valid_majorities": 551}, "multi_hop/score": {"agreement": 1.0, "correct": 454, "failed_or_no_majority": 5, "valid_majorities": 454}, "numeric/choice": {"agreement": 0.9952904238618524, "correct": 634, "failed_or_no_majority": 5, "valid_majorities": 637}, "numeric/noul": {"agreement": 1.0, "correct": 564, "failed_or_no_majority": 0, "valid_majorities": 564}, "numeric/score": {"agreement": 0.9978118161925602, "correct": 456, "failed_or_no_majority": 7, "valid_majorities": 457}, "probability/choice": {"agreement": 0.9149606299212598, "correct": 581, "failed_or_no_majority": 23, "valid_majorities": 635}, "probability/noul": {"agreement": 1.0, "correct": 562, "failed_or_no_majority": 0, "valid_majorities": 562}, "probability/score": {"agreement": 0.9821029082774049, "correct": 439, "failed_or_no_majority": 19, "valid_majorities": 447}, "temporal/choice": {"agreement": 0.9689542483660131, "correct": 593, "failed_or_no_majority": 33, "valid_majorities": 612}, "temporal/noul": {"agreement": 0.9945848375451264, "correct": 551, "failed_or_no_majority": 3, "valid_majorities": 554}, "temporal/score": {"agreement": 0.9707207207207207, "correct": 431, "failed_or_no_majority": 19, "valid_majorities": 444}}`.

## Teacher disagreements

Found 138 valid-majority disagreements; full records are in `runs/decisions/full/code_disagreements.jsonl` for inspection.
- Authored nano-majority vs gpt-4.1-mini agreement: 5451/6230 (87.5%).

## Data-quality review

- Decontamination removed 1,925 of 3,673 labeled states by 13-gram match. Only 301 of 2,224 labeled code states (1,313 questions) survived: temporal 128, probability 172, numeric 1, and none from counting, multi-hop, or long-policy. The pilot scan flagged 1,923 rows; a sampled exact overlap was `the batch has 0 1 eligible referrals the batch has 2 3 eligible`. This is a substantial code-family skew after filtering, despite the generated code-family mix being balanced.
- Five sampled code-gold disagreements were checked against their source facts; all five golds were consistent: INC-4100 resolves through AC-2200 → AGR-3100 → Core (10 hours), plus Central handling (5), for 15 hours; proposal A's 45% success rate exceeds B's 25%; five counting rows meet all filters; seven business days after 2024-12-22, excluding weekends and 2024-12-25, is 2025-01-01; and the $120 purchase totals $104.55 after discount and fee, a 12.875% change (score level 2). These spot checks do not validate every disagreement.

## Rejections

- Author rejections: 50; reasons `{"KeyError: 'answer'": 3, "KeyError: 'key'": 1, "ValueError: author response must contain 3\u20136 questions": 4, "ValueError: q1: authored answer '4' is not an option": 4, "ValueError: q2: authored answer '4' is not an option": 6, "ValueError: q2: authored answer '5' is not an option": 1, "ValueError: q3: authored answer '4' is not an option": 10, "ValueError: q3: authored answer '5' is not an option": 3, "ValueError: q4: authored answer '4' is not an option": 5, "ValueError: q4: authored answer '5' is not an option": 4, "ValueError: q5: authored answer '4' is not an option": 3, "ValueError: q5: authored answer '5' is not an option": 4, "ValueError: q6: authored answer '4' is not an option": 1, "ValueError: q6: authored answer 'priority_then_attach_then_attest_placeholder' is not an option": 1}`.
- Label/decontamination rejections: 1365; reasons `{"code teacher majority disagreed or label incomplete": 279, "nano majority and gpt-4.1-mini argmax disagree or label incomplete": 1086}`.
- Failed label calls: 828.
- API retry events after concurrency resume: `{}`; earlier requests have no transient-429 telemetry.

## Decontamination

Counts before filtering are in `rows_before`, `questions_before`, and `pilot_overlaps_before`; the after-filter overlap counters must be zero.
```json
{
  "rows_before": 3673,
  "rows_after": 1748,
  "questions_before": 15174,
  "questions_after": 6754,
  "dropped_text_13gram_rows": 1925,
  "dropped_option_questions": 3,
  "pilot_reference_rows": 48,
  "pilot_reference_questions": 171,
  "pilot_overlaps_before": {
    "word_13gram_rows": 1923,
    "option_set_questions": 2890
  },
  "remaining_overlaps": {
    "word_13gram": 0,
    "option_sets": 0
  }
}
```

## Split and rendering

- Train states: 1661; dev states: 87.
- Datum statistics: `{"datum_count": 6754, "mean_rendered_tokens": 840.3929523245484, "p95_rendered_tokens": 1425}`.

## Completion

- Data was uploaded privately to `jonsnov/muselet-decisions-v1`.
