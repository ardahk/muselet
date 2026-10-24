# Planner teacher demonstrations v1 — report

Code: `training/planner_demos/`. Data: private HF dataset `jonsnov/muselet-planner-demos-v1` @ 9453ff6 (code 99df4b6). No Tinker runs.

## Pipeline
1. `build_states.py`: 130 v2-tune states (from `evals/planner_scenarios_v2.jsonl`) plus synthetic states from `states_a.py` /
   `states_b.py`, built with the v2 builder (`planner_v2_lib.Screen` and the per-state `accept_first` / `reject_any` /
   `confirm_before` rules). Every synthetic state must pass the v2 validator checks: every gold reply passes the v1 grader
   (runtime and strict), every wrong reply and every generic negative fails, gold refs exist, skill args match the catalog,
   and the observation passes lint. 0 states were invalid.
2. `gate.py`: the router's hard decontamination gate applied to goals: exact match, a shared 13-gram, or token edit distance ≤ 1
   for items of ≤ 5 tokens. CJK counts one token per character. Gated against v2-holdout, v1 tune/holdout/holdout2,
   `evals/live_t1.jsonl` and all of `evals/external/utterances.jsonl` (HobbyLM sealed r1–r4, calc, system-settings; DeskMind
   diag/dyn/proposals). A state is also dropped if its (goal, observation) equals a v1 or v2-holdout scenario.
   The current gate also includes every turn utterance in `evals/memory_followups.jsonl`; counts below are from the earlier run.
   Dropped: 44 states ({"short_edit1": 24, "exact": 27}; by eval {"v1/holdout": 3, "v2-holdout": 37, "external/hobbylm/sealed-r1": 2, "external/hobbylm/sealed-r2": 3, "external/hobbylm/sealed-r4": 1, "v1/tune": 1, "live_t1": 4}).
   No state left after the gate overlaps any eval item (asserted in the code).
3. `render.py`: prompts are built exactly as the runtime builds them. The system prompt is `planner_prompt(catalog_desc(...))`
   from `prompts/planner_system.md`, **without** the few-shot block. The user message is `Planner.user_message`, with DSL history,
   no hint, and `login_page` set by the orchestrator's regex. `brain.planner` is imported with its MLX/torch deps stubbed.
4. `teachers.py`: gpt-5.6-sol (reasoning_effort=medium) and claude-opus-5-5 (no extended thinking, cached system prompt).
   Both get the same messages and no extra instructions.
5. `keep.py`: each reply is parsed into lines the way the runtime stream parses them (BatchCutter: ≤ 5 actions), then graded
   with `planner_offline.grade`. A state is kept only if **both** replies pass runtime and strict and neither reply
   overwrites non-empty field text (`type` replaces the field; search, address and header fields and placeholders are exempt).
   The target is the shorter passing reply. `bank.jsonl.gz` is the retrieval bank: goal, app, category, observation header and
   the batch, each < 400 Qwen3.5 tokens (tokenizer from mlx-community/Qwen3.5-4B-4bit).

## Results
States sent to the teachers: **1496**. Kept demos: **1194**. Retrieval bank: 1194 (0 were over 400 tokens).

| teacher | passes (runtime + strict + no clobber) |
|---|---|
| gpt-5.6-sol | 1232 / 1496 (82.4%) |
| claude-opus-5-5 | 1269 / 1496 (84.8%) |
| both pass (kept) | 1194 (79.8%) |

Teacher agreement:
- When both replies pass, the first op agrees in 1119/1194 (93.7%) and the full first line in 507/1194 (42.5%).
- Pass/fail verdicts agree on 1383/1496 states (92.4%).
- The kept target is Anthropic's reply 713 times and OpenAI's 481 times.

Why states were dropped: {"anthropic_fail": 38, "both_fail": 189, "openai_fail": 75}. Reasons teacher replies failed:
- gpt-5.6-sol: {"wrong_first_action": 247, "rejected_line": 11, "invalid_dsl": 6}
- claude-opus-5-5: {"wrong_first_action": 205, "rejected_line": 14, "invalid_dsl": 6, "strict_fail": 2}

| family | sent to teachers | after gate | openai pass | anthropic pass | kept |
|---|---|---|---|---|---|
| calculator | 65 | 65 | 65 | 63 | 63 |
| finder_close | 45 | 45 | 31 | 36 | 31 |
| finder_find | 75 | 73 | 47 | 41 | 39 |
| finder_move_rename | 70 | 70 | 59 | 70 | 59 |
| finder_new_folder | 110 | 110 | 109 | 110 | 109 |
| finder_view | 70 | 66 | 65 | 65 | 64 |
| followup | 130 | 130 | 110 | 129 | 110 |
| mixes | 130 | 114 | 109 | 111 | 106 |
| permission | 135 | 135 | 35 | 34 | 26 |
| settings | 95 | 93 | 86 | 91 | 84 |
| sign_in | 125 | 114 | 114 | 114 | 114 |
| timers | 50 | 50 | 40 | 39 | 39 |
| v2_tune | 130 | 121 | 94 | 90 | 85 |
| web_answer | 160 | 160 | 146 | 149 | 146 |
| writing | 150 | 150 | 122 | 127 | 119 |

Kept by app: Finder 247 · Safari 161 · Zen 132 · Google Chrome 115 · Notes 108 · System Settings 89 · Mail 81 · Messages 56 · Pages 52 · Calculator 48 · TextEdit 35 · Slack 24 · Clock 11 · SecurityAgent 10 · Calendar 8 · Reminders 5 · Keynote 3 · Preview 3 · Adobe Premiere Pro 2026 3 · Numbers 1 · WhatsApp 1 · UserNotificationCenter 1.
Kept by category: finder 263 · web_answer 146 · writing 126 · sign_in 122 · compound 116 · done_gating 78 · settings 60 · confirm 48 · ask 45 · calculator 40 · timers 32 · recovery 28 · permission 26 · followup 26 · injection 22 · single_step 11 · script 5.

## Spend
Pilot (60 states) plus the full run: **$12.71** of the $90 budget. Prices are $4 in / $20 out per 1M tokens
for both models. OpenAI cached input is counted at 25%; Anthropic cache reads at 10% and cache writes at 125% (conservative).
There was also a $0.06 smoke test.

## Notes for the lead
- **Permission prompts are a teacher blind spot.** Only 26 of 135 states were kept: without the few-shot rules, both
  teachers usually carry on with the user's task instead of asking. The kept 26 are the right behaviour (ask), but the
  family is thin. Options: a code gate (cloud/builder_brain8 already specifies one), or a teacher prompt addendum for
  that family only. The second would break the "exact system prompt" rule, so I didn't do it.
- `finder_find` (39/73 kept) and `finder_close` (31/45) lose many states when a teacher guesses a path or checks with a
  script instead of reading the window. Those replies are rejected, as intended.
- The grader is conservative, so some reasonable replies were dropped. For example, focusing a note with press plus
  `expect focused` and then `skill type_text` in the same batch was rejected on "not focused" states. Dropping only shrinks
  the data; it never adds a wrong demo.
- v2 benchmark bug (merged in PR #29): the gold/accept rules of v2-pages-no-target, v2-notes-into-search,
  v2-notes-text-missing, v2-note-delete-others, v2-doc-sysprompt, v2-pages-append, v2-note-checklist-item and
  v2-pages-type-save append with `type #ref "\n…"`, which replaces the field. The demos are protected by the
  clobber filter. The v2 rules need a follow-up fix (not done here: no `evals/` edits in this PR).
