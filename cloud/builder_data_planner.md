# Cloud builder: data-planner (bigger planner benchmark + teacher demonstrations) — Muselet

Repo `ardahk/muselet`. Read `AGENTS.md` (observation format, action DSL), `prompts/planner_system.md`,
`prompts/planner_fewshot.md`, and `evals/planner_offline.py`: 51 hand-written scenarios with tune / holdout / holdout2
sets. Its grading is runtime-equivalent through `dsl.action_line`, and checks first action, reject list and
confirm-before. Branch `cloud/data-planner`, one PR. Don't edit existing scenarios, the grader, prompts or the
planner; add new files only.

1. **Planner benchmark v2.** 250+ new scenarios in `evals/planner_scenarios_v2.jsonl`, same fields as `sc()`.
   - AX observations must be realistic for macOS 27 apps. Reproduce the real role and label vocabulary from
     `app/Sources/HandsKit/Observe.swift` (kRoleMap, labels), Finder, Safari/Zen/Chrome web AX, Mail, Messages,
     Notes, Numbers, Calendar, Reminders, System Settings, Preview, Pages, Keynote, Slack, Premiere (blind).
   - Categories, balanced: single-step, recovery after a failed batch, done-gating, ask-for-missing-info,
     confirm-before-irreversible, prompt injection, sign-in pages, writing content, compound goals, script use.
   - Accept/reject regexes must be precise. Every scenario needs at least one gold reply that passes the grader and
     one plausible wrong reply that fails it. Add a validation script that checks both automatically.
   - Split 50/50 into v2-tune and v2-holdout by category.
2. **Teacher demonstrations** for a possible planner LoRA later (the lead decides the Tinker spend separately).
   - Two frontier teachers (OpenAI + Anthropic) answer each v2-tune scenario and 1,000+ extra synthetic scenarios,
     using the exact planner system prompt.
   - Keep only replies that pass the grader and agree in their first action. Store them as chat datums in the
     planner's DSL history format.
   - Never use v2-holdout or any existing scenario as training data.
3. **Deliver:** the scenarios, the validation script, and `evals/planner_v2_REPORT.md` (counts, category balance,
   validation results, teacher pass rates). Upload demonstrations to a private HF dataset `jonsnov/muselet-planner-demos-v1`.
   Budget: up to $90 API total; report the spend.
Reply when the benchmark (step 1) is ready for the lead to review. The lead reviews a sample before anything is adopted.
