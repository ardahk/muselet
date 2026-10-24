# System One decisions: research, data plan and hypotheses

Goal: beat DeskMind brain-4b G18b on its own benchmarks (JevBench public, typed-decisions test) with Muselet's System 1
(Qwen3.5-4B + Tinker LoRA, one forward pass, choice-token logits after a prefilled `choice#`), without losing route
accuracy or speed.

Starting point (measured by the lead on the M5 Pro, official runners, same shim):

| model | JevBench public | easy / original / hard | typed-decisions test | choice / noul / score |
|---|---|---|---|---|
| Muselet base Qwen3.5-4B-4bit, zero-shot | 0.719 | 1.000 / 0.833 / 0.523 | 0.569 | 0.557 / 0.667 / 0.505 |
| DeskMind brain-4b G18b (8-bit) | 0.831 | 1.000 / 0.958 / 0.676 | 0.658 | 0.657 / 0.702 / 0.626 |

The gap is concentrated in the JevBench hard tier (−15 pts) and `score` questions (−12 pts).

## 1. DeskMind's recipe

Sources: training doc <https://github.com/deskmind-ai/brain/blob/main/docs/training.md>, results
<https://github.com/deskmind-ai/brain/blob/main/docs/results.md>, trainer
<https://github.com/deskmind-ai/brain/blob/main/src/deskmind_brain/train/train.py>, HF blog
<https://huggingface.co/blog/gxcsoccer/deskmind-local-decision-models>, launch post <https://deskmind.dev/blog/launch/>,
model card <https://huggingface.co/deskmind/brain-4b>. Checkout used: commit `dadf97d`.

**Item types and mix.** Typed questions (choice / yes-no / score) over web and form tasks, desktop tasks, and
evidence questions; labels come from a teacher distribution, with hosted frontier models generating synthetic tasks
(the generators are not in the repo) [training.md; model card]. Desktop states come from DAgger-style rollouts with
oracle labels, and unlabelled questions are kept so that the prompt shape is the same at train and serve time
[training.md]. A general base mix samples HF train splits (banking77, emotion, MMLU aux_train, BoolQ, tweet_hate,
SST-2, toxic_chat, HelpSteer2, Amazon reviews; 800 per task)
<https://github.com/deskmind-ai/brain/blob/main/src/deskmind_brain/train/data.py>, plus Mind2Web element choice with
10–90 option windows <https://github.com/deskmind-ai/brain/blob/main/src/deskmind_brain/train/mind2web.py>. The G18b
mix has **100,703 items** [results.md].

**Loss.** `L = 0.7·KL(teacher‖student) + 0.3·CE(gold)` (alpha default 0.7); gold is drawn at random among tied
maxima of the soft reference [train.py].

**LoRA / optimisation.** r=16, alpha=32, dropout 0.05 on all attention, MLP and linear-attention projections
(`in_proj_qkv`, `in_proj_z`, `out_proj`); AdamW with OneCycle (pct_start 0.1), lr 1e-4 default, 5e-5 in the
documented command (`--prompt-format 2 --shuffle-options --round-size 52 --compact-targets --max-tokens 8192
--batch-size 4`) [train.py; training.md].

**Counterexamples against shortcuts.** Options are shuffled because authored requests list the right answer first far
more often than chance [train.py]. `scripts/shortcut_counterexamples.py` adds `corrupt_done`, `sibling_done` and `ask`
families (an undo button, a saved document, a second window, ambiguous source records) so that surface cues stop
predicting the label
<https://github.com/deskmind-ai/brain/blob/main/scripts/shortcut_counterexamples.py>. The blog lists two lessons:
the prompt shape leaked the label (done examples had fewer questions), and a fixed 0.95 soft label collapsed the 0.8B
model's confidence into 0.94–0.97 [blog]. Later rounds learn from 4B probabilities instead [blog]. Other documented
lessons: oracle-label only what the harness can see, probe with real failing requests, and note that offline holdouts
do not catch shortcuts [training.md]. About 20 rounds cost roughly $600 [launch post].

**Tier movement G14 → G18b (4B, JevBench v1.4.2 public).** G10b 47/71/80 (0.857), G14 48/67/85 (0.866), G18b
48/69/76 (0.835). "The hard tier drops 85→76, mostly temporal/numeric, hard-judgement and multi-hop items. G18b's mix
leans further toward desktop states, and general judgement suffered" [results.md]. Calibration got worse: Brier
0.230→0.269 and ECE 0.079→0.089 [results.md]. 4-bit changes about 30% of answers versus 8-bit at the same speed
[results.md].

**Contamination check.** Word 13-grams (regex `[a-z0-9]+`, with `'` and `.` joins and CJK per character) over
state + instructions + criteria. An item is also flagged when its option set equals a public label set that has at
least 3 labels and is used by at most 2 items
<https://github.com/deskmind-ai/brain/blob/main/scripts/contamination_check.py>. Reported result: the 100,703-item
mix shares no 13-gram and no option set with the 231 public items [results.md].

**Takeaway.** DeskMind's own regression shows that its hard-tier strength came from general reasoning and judgement
data. Diluting that data with desktop states cost 9 hard items. Our base model is weakest exactly there.

## 2. typed-decisions

Dataset card <https://huggingface.co/datasets/LocalLLaMA/typed-decisions> (Apache-2.0, pinned revision `80cb93a`):

- **Structure.** 4 workflows (agent_trace_observability, customer_service, invoice_processing, security_incidents),
  each with 300 train and 100 test cases of 5 questions; the test split has 400 cases and 2,000 decisions.
- **Gold labels.** Gold is the mean of 3 teacher samples at T=0.7, from "a teacher of roughly 4B-class capability".
  The score therefore measures agreement with that teacher.
- **Reference points.** Prior 0.470, perfect factor recovery 0.704, teacher self-agreement 0.735. Per-question
  ceilings range from 0.560 (agent_trace urgency) to 0.937.
- **Zero-shot leaderboard.** d3-mini (4B) 0.743 (KL 0.319, Brier 0.123, ECE 0.047); Liquid d1 0.742 (KL 0.475).
  Third-party HF Jobs scoring <https://huggingface.co/datasets/LocalLLaMA/typed-decisions/discussions/37>.
- **Fitted leaderboard.** Decider-4B 0.8205 (KL 0.301, ECE 0.031); pramana-2b 0.8005 (KL 0.0755); od1 0.797.

Recipes:

- **Decider-4B** <https://huggingface.co/roudone/Decider-4B>,
  <https://huggingface.co/datasets/LocalLLaMA/typed-decisions/discussions/36>.
  - Init and training: Qwen3.5-4B weights, then LoRA plus a pointer decision head, trained on "collected decision
    datasets" including the train split.
  - Calibration: one global temperature fit (CE) on held-out validation soft labels; exported T=1.0.
  - Latency: 117 ms per case on an A800.
- **pramana-2b / 0.8b** <https://huggingface.co/apracv/pramana-2b>,
  <https://huggingface.co/datasets/LocalLLaMA/typed-decisions/discussions/46>.
  - Training: train split only, with 80 train cases held out for temperature. Loss is CE against soft gold plus a
    Brier term (weight 1.0). Two averaged LoRAs (lr 2e-4 and 1e-4).
  - Calibration: KL and ECE want different temperatures, so probabilities use T_p≈1.00–1.05 fitted to soft gold,
    and confidence uses a separate T_c fitted to hard labels. Fitting T to hard labels after soft training
    sharpened it 3× (T=0.343) and pushed KL from 0.076 to 0.50.
  - By type: choice 0.767, noul 0.858, **score 0.782**. Transfer outside the benchmark is poor (CLINC150 0.572,
    Banking77 0.255), the cost of specialising.
- **od1** <https://huggingface.co/mvbalaji/od1-typed-decisions>.
  - Training: Qwen3.5-4B full FT on 1,080 train cases (5,400 decisions), CE against soft gold, LR 5e-6, heads 3e-4,
    3 epochs.
  - Results: under-confident (ECE 0.157). noul was trained without true/false definitions. Weakest heads:
    agent-trace urgency 0.57, outcome 0.65, CS action 0.68.
  - Template overlap: 23.5% of test states share ≥50% of their 13-grams with train, so fitting on train is partly
    template matching.
- **d3-mini** <https://huggingface.co/vllm-sr/d3-mini>: 4B, one forward pass per typed question, zero-shot 0.743. The
  card does not disclose training data.

`score` questions: in TD, scores are ordinal levels with descriptions and gold is a soft distribution over levels, so
argmax accuracy rewards matching the teacher's typical (often central) level. Pramana's score 0.782 versus our 0.505
shows that learning the level semantics is learnable and worth roughly 25 points when fitted. Zero-shot, the lever is
generic ordinal-rubric training with soft labels.

## 3. JevBench

Repo <https://github.com/fstandhartinger/jevbench> at the runner's pinned commit `609a664` (v1.4.2-compatible public
data):

- **Public tiers (231 items).**
  - easy 48: intent / fact / extraction / tool_selection, 12 each; 36 choice, 12 noul.
  - original 72: policy / intent / ordinal / extraction / adequacy / routing, 12 each; 36 choice, 24 noul, 12 score.
  - hard 111: long_policy 19, multi_hop 18, judge_hard 17, temporal_numeric 15, probability 10, trap 8,
    ambiguous 7, tradeoff 6, adversarial 6, routing_hard 5. 67 choice, 38 noul, 6 score. Label counts:
    2 (38 items), 3 (15), 4 (37), 5 (17), 6 (4).
- **Hard-tier semantics** <https://github.com/fstandhartinger/jevbench/blob/main/datasets/HARD-TIER.md>.
  - Size and authorship: 220 items (111 public, 109 held out), authored by frontier models and cross-reviewed.
  - long_policy: 2–6k-token states with 3–6 interacting conditions.
  - temporal_numeric: time zones, business days, leap years, pro-rating, ≥ vs >.
  - ambiguous: about half have gold `insufficient_information`. trap: a surface answer is wrong.
  - Format: noul labels `[no, yes]` with true/false criteria; choice has 3–7 labels, score 3–6 levels; golds are
    balanced and never placed first.
- **Scoring and rules.**
  - Disclosure: "Training on the public split must be disclosed" [README]. "Training on open items is allowed and
    disclosed"; training and calibration must never read the sealed pool
    <https://github.com/fstandhartinger/jevbench/blob/main/docs/METHOD-v1.5.md>. A public-to-sealed gap above
    25 pts reduces the Intelligence score [README].
  - Option-order sensitivity: small models are very sensitive to option order (a 72%→21% swing with reversed
    yes/no order) [README].
- **Our rule.** We never train on public items, and we decontaminate against them. No sealed data is available to us.

## 4. Public datasets usable as decision training data

| competency | dataset | license | use |
|---|---|---|---|
| numeric/table, multi-hop numeric | TAT-QA <https://huggingface.co/datasets/next-tat/TAT-QA> | CC-BY-4.0 | seed tables → threshold/compare decisions, code gold |
| numeric reasoning | FinQA <https://huggingface.co/datasets/ibm-research/finqa> | CC-BY-4.0 | seed facts, code gold |
| multi-hop yes/no | StrategyQA <https://huggingface.co/datasets/ChilleD/StrategyQA> | MIT | noul with evidence paragraphs |
| policy/contract judgement | CUAD <https://huggingface.co/datasets/theatticusproject/cuad-qa> | CC-BY-4.0 | clause-applies choice/noul |
| policy (NC, hackathon only) | ContractNLI <https://huggingface.co/datasets/kiddothe2b/contract-nli> | CC-BY-NC-SA-4.0 | entail/contradict/not-mentioned (track in `data/LICENSES.md`) |
| temporal | TRACIE <https://huggingface.co/datasets/tasksource/tracie>, temporal-nli <https://huggingface.co/datasets/tasksource/temporal-nli> | Apache-2.0 | temporal-order noul |
| rule reasoning | RuleTaker <https://huggingface.co/datasets/tasksource/ruletaker> | Apache-2.0 | multi-condition rules → noul |
| agent-step / forms | Mind2Web <https://huggingface.co/datasets/osunlp/Mind2Web> | CC-BY-4.0 | next-element choice over large option sets |
| judgement (NC) | ANLI <https://huggingface.co/datasets/facebook/anli> | CC-BY-NC-4.0 | adversarial entailment as noul |

Excluded:

- HotpotQA (CC-BY-SA-4.0, share-alike) <https://huggingface.co/datasets/hotpotqa/hotpot_qa>.
- Benchmark suites (BIG-bench, LegalBench), so that we don't train on someone's eval.

Licenses are taken from the HF repo license tags and need to be re-checked against each upstream before use. Public
seeds stay a minority (≤20%). The bulk is synthetic so that it can match the System One schema exactly.

## 5. Hypotheses (to be confirmed or refuted in `training/decisions/reports/`)

- **H1, code-verified reasoning data moves the hard tier most.**
  - Data: about 40% of decisions in programmatically generated families: temporal (business days, time zones,
    leap years, pro-rating, inclusive/exclusive deadlines), numeric thresholds/comparisons/counting, multi-hop lookups
    over records and tables, and long multi-condition policies (2–6k-token states, gold evaluated by a rule engine).
  - Labels: teacher soft labels, kept only when the teacher argmax equals the code gold.
  - Prediction: hard 0.52 → ≥0.68 (+18 items, mostly temporal_numeric, multi_hop and long_policy, i.e. 52 public
    items where base is weakest).
  - Why: DeskMind's hard drop was in these families when such data was diluted [results.md]; these are skills a 4B
    model has but does not apply reliably in one forward pass without practice.
- **H2, ordinal score training moves `score` +10–15 pts** (TD score 0.505 → ≥0.62; JevBench ordinal/score items).
  - Data: about one third of decisions are score questions with 3–6 described levels and soft teacher
    distributions, spanning severity, urgency, quality and priority rubrics.
  - Why: pramana shows score is very learnable [pramana card]. The base model's score errors look like ignorance of
    the level semantics, which generic rubric data addresses without TD data.
- **H3, judgement, ambiguity and traps.** Teacher-labelled judge/tradeoff/adequacy/ambiguous
  (`insufficient_information` gold on about 15% of those) and trap/adversarial items add +4–6 hard items and
  +3 original items. DeskMind G14 → G18b lost general judgement when it was underweighted [results.md].
- **H4, format robustness.**
  - Method: options shuffled per sample, gold position balanced, noul shown in both orders where the schema allows,
    option counts uniform over 2–12 (with a tail to 26 via the tournament), and 1–6 questions per state, so prompt
    shape cannot leak the label.
  - Prediction: protects against the order sensitivity JevBench documents [README; DeskMind train.py].
  - This is a robustness hypothesis: we expect it to prevent regressions rather than add points by itself.
- **H5, soft labels plus temperature.**
  - Labels: mean of several teacher samples (and token logprobs where the API gives them). Loss: the route
    pipeline's soft-label loss.
  - Calibration: a single temperature fit on our synthetic dev split, with separate probability and confidence
    temperatures if KL and ECE disagree (pramana's finding).
  - Prediction: TD KL ≤ 0.35 and ECE ≤ 0.06 (G18b JevBench calibration: Brier 0.269, ECE 0.089).
- **H6, multitask route replay.** At least 30% route datums in the mix keep route_v1 top-1 and macro-F1 within 1 pt of
  cloud A's route-only adapter, because the route task uses the same renderer and answer position.
- **Overall prediction.** JevBench public 0.719 → 0.84–0.87 (hard 0.68–0.76). typed-decisions zero-shot 0.569 →
  0.66–0.70, above G18b's 0.658 but below d3-mini's 0.743, because TD rewards agreement with a specific 4B teacher's
  workflow conventions that we deliberately don't fit.
- **Main risk.** Teacher-label style versus benchmark gold style, especially for score and ambiguous items.
  Mitigations: two teacher families averaged, and code gold wherever possible.
