# HobbyLM request coverage

Primary ranking is the 125-task sealed r4 live set. The remaining columns are separate frozen sources.
Only implementation gaps confirmed by the catalog and execution path are ranked; model-routing quality needs live evaluation.

| Rank | Confirmed gap | r4 live (IDs) | r1–r3 frozen (IDs by round) | calc-tasks (IDs) | System Settings (IDs) | Evidence |
|---:|---|---|---|---|---|---|
| 1 | Arithmetic word problems not parsed by calc | 20: C07, C08, C09, C10, C11, C12, C13, C14, C15, C17, C20, C22, C23, C24, C25, C26, C27, C28, C29, C30 | r1 20: C07, C08, C09, C10, C11, C12, C13, C14, C15, C17, C20, C22, C23, C24, C25, C26, C27, C28, C29, C30; r2 20: C07, C08, C09, C10, C11, C12, C13, C14, C15, C17, C20, C22, C23, C24, C25, C26, C27, C28, C29, C30; r3 20: C07, C08, C09, C10, C11, C12, C13, C14, C15, C17, C20, C22, C23, C24, C25, C26, C27, C28, C29, C30 | — | — | ml/tests/test_hobby_gaps.py:26-30; ml/src/brain/calc.py:437-453 |
| 2 | Event requests with people cannot create invitees | 20: E01, E02, E03, E04, E05, E06, E07, E08, E09, E10, E11, E12, E13, E14, E15, E16, E17, E18, E19, E20 | r3 8: E01, E02, E03, E04, E05, E06, E07, E08 | — | — | skills/catalog.json:74-79; app/Sources/HandsKit/Skills.swift:922-944 |
| 3 | Native System Settings navigation is not implemented | — | — | — | 15: D1, D2, D3, H01, H02, H03, H04, H05, H06, H07, H08, H09, H10, H11, H12 | skills/catalog.json:10-114; app/Sources/HandsKit/Skills.swift:360-520 |

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

- EventKit `create_event` has no calendar argument and always uses the default calendar (`skills/catalog.json:74-79`; `app/Sources/HandsKit/Skills.swift:922-944`). The replay harness therefore requires `Muselet Bench` to be a local default calendar; frozen tasks do not request choosing a different calendar.
- Countdown timers are executable through `start_timer`; the replay grades its successful RPC result and discloses whether timers were canceled. Relative reminder wording remains a live-routing risk.
- Event text is routed through the catalog-backed `DecisionEngine.route` and `DecisionEngine.args`; datetime and duration arguments are normalized in `Orchestrator._coerce_typed`. No natural-language routing failure is claimed from the unused v0 regex router.
- Relative volume, mute paraphrases, agenda lookup, and unknown-intent false positives are not ranked from the unused v0 regex router; these require live model evaluation.
- Timezone-qualified date parsing and Hinglish are listed only as unverified live-evidence risks above.
- Calculator arithmetic uses the existing deterministic grammar; unhandled r4 word problems are ranked above. Timer, Bluetooth, lock-screen, and empty-Trash paths are implemented in HandsKit. Brain-executor dispatch is present in the orchestrator. Directional brightness is implemented through the HandsKit delta argument (`skills/catalog.json:20-24`; `app/Sources/HandsKit/Skills.swift:418-437,807-808`). Event invitees and native System Settings navigation remain unimplemented. Evidence: `ml/src/brain/calc.py:437-453`; `ml/src/brain/orchestrator.py:296-302,346-356,405-422,433-481,695-747`; `app/Sources/HandsKit/Skills.swift:373-380,471-482`.
