# HobbyLM request coverage

Primary ranking is the 125-task sealed r4 live set. The remaining columns are separate frozen sources.
Only implementation gaps confirmed by the catalog and execution path are ranked; model-routing quality needs live evaluation.

| Rank | Confirmed gap | r4 live (IDs) | r1–r3 frozen (IDs by round) | calc-tasks (IDs) | System Settings (IDs) | Evidence |
|---:|---|---|---|---|---|---|
| 1 | Calculator/arithmetic has no executable skill or route | 30: C01, C02, C03, C04, C05, C06, C07, C08, C09, C10, C11, C12, C13, C14, C15, C16, C17, C18, C19, C20, C21, C22, C23, C24, C25, C26, C27, C28, C29, C30 | r1 30: C01, C02, C03, C04, C05, C06, C07, C08, C09, C10, C11, C12, C13, C14, C15, C16, C17, C18, C19, C20, C21, C22, C23, C24, C25, C26, C27, C28, C29, C30; r2 30: C01, C02, C03, C04, C05, C06, C07, C08, C09, C10, C11, C12, C13, C14, C15, C16, C17, C18, C19, C20, C21, C22, C23, C24, C25, C26, C27, C28, C29, C30; r3 30: C01, C02, C03, C04, C05, C06, C07, C08, C09, C10, C11, C12, C13, C14, C15, C16, C17, C18, C19, C20, C21, C22, C23, C24, C25, C26, C27, C28, C29, C30 | 34: D01, D02, D03, D04, simple-01, simple-02, simple-03, simple-04, simple-05, simple-06, simple-07, simple-08, simple-09, simple-10, reversed-11, reversed-12, reversed-13, reversed-14, reversed-15, reversed-16, reversed-17, reversed-18, messy-19, messy-20, messy-21, messy-22, messy-23, messy-24, messy-25, messy-26, messy-27, messy-28, messy-29, messy-30 | — | skills/catalog.json:4-8,10-113; ml/src/brain/orchestrator.py:143-165; app/Sources/HandsKit/Skills.swift:186-371 |
| 2 | Event requests with people cannot create invitees | 20: E01, E02, E03, E04, E05, E06, E07, E08, E09, E10, E11, E12, E13, E14, E15, E16, E17, E18, E19, E20 | r3 8: E01, E02, E03, E04, E05, E06, E07, E08 | — | — | skills/catalog.json:72-73; app/Sources/HandsKit/Skills.swift:571-584 |
| 3 | Countdown timers have no executable start_timer implementation | 8: T01, T02, T03, T04, T05, T06, T07, T08 | r1 8: T01, T02, T03, T04, T05, T06, T07, T08; r2 8: T01, T02, T03, T04, T05, T06, T07, T08; r3 8: T01, T02, T03, T04, T05, T06, T07, T08 | — | — | skills/catalog.json:69-70; app/Sources/HandsKit/Skills.swift:186-371 |
| 4 | Directional brightness has no relative adjustment skill | 6: D01, D02, D03, D04, D05, D06 | r1 6: D01, D02, D03, D04, D05, D06; r2 6: D01, D02, D03, D04, D05, D06; r3 6: D01, D02, D03, D04, D05, D06 | — | — | skills/catalog.json:20-21; app/Sources/HandsKit/Skills.swift:206-211,439 |
| 5 | Native System Settings navigation is not implemented | — | — | — | 15: D1, D2, D3, H01, H02, H03, H04, H05, H06, H07, H08, H09, H10, H11, H12 | skills/catalog.json:4-8,10-113; ml/src/brain/orchestrator.py:143-165; app/Sources/HandsKit/Skills.swift:186-371 |

## Risks pending live evidence

These are hypotheses, not confirmed gaps. They remain unverified until the Muselet live replay runs.
Ranked by the number of matching r4 tasks; `none` IDs include the likely catalog skill or route.

| Rank | Unverified risk | r4 count (IDs / likely route) |
|---:|---|---|
| 1 | None-set requests may hit an acting catalog route (HobbyLM grades any action as failure) | 12: N01 (`web_search`); N02 (`send_message`); N03 (`open_url`); N04 (`MULTI_STEP`); N07 (`play_music`); N08 (`finance_review`); N09 (`open_app`); N10 (`start_timer`); N11 (`find_file`); N13 (`web_search`); N14 (`web_search`); N16 (`web_search`) |
| 2 | Timezone-qualified event times may be parsed or normalized differently | 10: E03; E04; E09; E11; E13; E14; E16; E18; E25; E30 |
| 3 | Hinglish/code-mixed requests may route differently | 3: C07; D08; A02 |
| 4 | Relative reminder wording may route as a timer or reminder | 3: T02; T04; T07 |
| 5 | A03-style requests may route to `todays_agenda`/`ANSWER` instead of leaving Calendar frontmost | 1: A03 |

## Audited but not ranked

- EventKit `create_event` has no calendar argument and always uses the default calendar (`skills/catalog.json:72-73`; `app/Sources/HandsKit/Skills.swift:575-584`). The replay harness therefore requires `Hobby Test` to be the default calendar; frozen tasks do not request choosing a different calendar.
- Relative `remind me in` / `ping me in` tasks are included in the timer gap (T02, T04, T07 in r4): `create_reminder` requires a title and optional ISO due date, while `start_timer` has no HandsKit case. No separate timer-vs-reminder count is added.
- Event text is routed through the catalog-backed `DecisionEngine.route` and `DecisionEngine.args`; datetime and duration arguments are normalized in `Orchestrator._coerce_typed`. No natural-language routing failure is claimed from the unused v0 regex router.
- Relative volume, mute paraphrases, agenda lookup, and unknown-intent false positives are not ranked from the unused v0 regex router; these require live model evaluation.
- Timezone-qualified date parsing and Hinglish are listed only as unverified live-evidence risks above.
- Catalog v2 also lists `bluetooth`, `lock_screen`, and `empty_trash` without HandsKit cases. `finance_review` and `advisor_prep` have brain-side modules, but `Orchestrator._skill` does not dispatch by the catalog `executor` field and HandsKit has no matching cases. These names do not occur in the frozen HobbyLM sets, so they are not ranked here (`skills/catalog.json:103-113`; `ml/src/brain/orchestrator.py:397-417`; `app/Sources/HandsKit/Skills.swift:157,381-383`).
