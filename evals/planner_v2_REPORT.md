# Planner benchmark v2 + teacher demonstrations — report

Branch `cloud/data-planner`. New files only: v1 scenarios, grader (`evals/planner_offline.py`), prompts and planner are untouched.

## Step 1 — benchmark v2 (ready for lead review)

**260 scenarios** in `evals/planner_scenarios_v2.jsonl`, same fields as `planner_offline.sc()`
(`id, tags, goal, observation, last_batch, script_output, accept_first, reject_any, confirm_before`) plus
`category`, `split`, `gold` (replies that must pass) and `wrong` (plausible replies that must fail).

### Category balance and split

| category | what it tests | v2-tune | v2-holdout |
|---|---|---|---|
| single_step | one obvious next action | 13 | 13 |
| recovery | last batch failed (stale_ref, focus_changed, no_text_target, expect_failed, not_frontmost, script exit, screen_locked) | 13 | 13 |
| done_gating | `done` only when observation / last batch / script result proves the goal | 13 | 13 |
| ask | value only the user can supply is missing or ambiguous | 13 | 13 |
| confirm | send/delete/buy/post/pay/overwrite needs `confirm` first; 5 `-> yes`/`-> no` follow-ups | 13 | 13 |
| injection | on-screen or script-output text carries instructions | 13 | 13 |
| sign_in | login / 2FA / passkey / captcha / SSO walls, plus credential-given and route-around cases | 13 | 13 |
| writing | content into the right text target, focus first in document apps | 13 | 13 |
| compound | multi-part goals, incl. half-done follow-ups | 13 | 13 |
| script | AppleScript/shell for sheet math, bulk files, app queries; read `Script result` back | 13 | 13 |
| **total** | | 130 | 130 |

Split is exact 50/50 per category. Same-goal groups inside a category (e.g. a confirm case and its `-> yes`
follow-up) always land in the same split, and no goal string appears in both splits or in any v1 scenario
(validator-enforced), so v2-tune can feed teacher data without leaking v2-holdout or v1.

### Apps (observation header)

Finder 49 · Google Chrome 24 · Safari 21 · Mail 20 · Zen 17 · System Settings 14 · Calendar 13 · Messages 13 · Slack 12 · Numbers 12 · Keynote 11 · Notes 10 · Pages 10 · Reminders 9 · Adobe Premiere Pro 2026 7 · TextEdit 7 · Preview 5 · Music 4 · Spotify 1 · WhatsApp 1.
Premiere is blind (only window chrome + the orchestrator's `Accessibility tree is empty here` hint). Chrome/Zen/Safari
use web-AX vocab (tab `radio`s, address field labels as each browser exposes them).

### Observation realism

Observations are built by `evals/planner_v2_screens.py` on top of `evals/planner_v2_lib.Screen`, which follows
`HandsKit/Observe.swift`: kRoleMap role names only (`button textfield textarea checkbox radio popup link slider menuitem
row cell combobox tab`, label-only `text`/`image`), interactive elements before labelled text/images, `value=` only on
textfield/textarea/combobox, `checked|unchecked` only on checkbox/radio, `selected`/`disabled` flags, static text cut at
80 chars (Observe.swift `prefix(80)`), header `app: … | window: "…"` with `| focused: #N` only when something is focused.
Refs are realistic non-sequential numbers per app and stay stable across derived screens (`Screen.set/add/drop`), so
`last_batch` refs line up with the observation; stale refs in `last_batch` are checked to be absent from it.
Last-batch lines use the orchestrator's `<dsl line> -> ok | failed: <error>` form with HandsKit error strings.

### Validation (`python3 evals/planner_v2_validate.py`, exit 0)

| check | result |
|---|---|
| scenarios / failing scenarios | 260 / 0 |
| gold replies pass the v1 grader (runtime **and** strict) | 300 / 300 |
| plausible wrong replies fail the grader | 379 / 379 (all parse as valid DSL — they fail on first action / reject / confirm order, not syntax) |
| generic negatives fail (empty reply, prose, `wait 300`, `done "Done"` unless gold is `done`) | 1004 / 1004 |
| gold `skill` lines match `skills/catalog.json` (name, args, required, enums) | pass |
| gold refs exist in the observation | pass |
| observation lint (roles, value/checked placement, ordering, header, 80-char text, unique refs) | pass |
| 50/50 split per category, no goal shared across splits or with v1 | pass |

Rebuild deterministically with `python3 evals/planner_v2_build.py` (scenarios live in `evals/planner_v2_cat_*.py`).
Run models with the unchanged v1 runner via `evals/planner_v2_run.py --v2-set v2-tune|v2-holdout …` (same flags as
`planner_offline.py`; never tune on v2-holdout).

### Known limits / review pointers

- Observations are hand-modelled from Observe.swift + app knowledge, not captured live on macOS 27 (no Mac here).
  Labels most worth a spot-check: Numbers `cell "A2 Milk"` style labels, Keynote/Pages toolbar, Slack desktop composer.
- App mix is not balanced per split (category balance was the requirement): e.g. Premiere 6 tune / 1 holdout.
- `accept_first` lists every reasonable first action we could think of; a model may still find another valid one.

## Step 2 — teacher demonstrations

Not started: waiting for the lead's review of step 1. API spend so far: **$0**.
