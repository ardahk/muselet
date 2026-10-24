# Phase 1 data fixes (training review 3/6/7/10/13/16)

Built by `python -m muselet_train.fixes --out v2all --from full1 v2new --ask-run ask2`, then `decontam`/`dedup`/`relabel_v2`.

## Eval decontamination (incl. evals/external/utterances.jsonl, 570 rows)

Drops are attributed to the first eval source that matched.

| run | set | in | kept | drops by eval source |
|---|---|---|---|---|
| full1 | route | 38716 | 37655 | external/hobbylm/sealed-r1 19, external/hobbylm/sealed-r2 49, external/hobbylm/sealed-r3 20, external/hobbylm/sealed-r4 32, hobbylm/hobbymac-sealed-test 139, hobbylm/hobbymac-sealed-test-r2 43, hobbylm/hobbymac-sealed-test-r3 19, hobbylm/hobbymac-sealed-test-r4 49, live_t1 126, route_v1 565 |
| full1 | args | 25542 | 24785 | external/hobbylm/sealed-r1 14, external/hobbylm/sealed-r2 46, external/hobbylm/sealed-r3 5, external/hobbylm/sealed-r4 28, hobbylm/hobbymac-sealed-test 89, hobbylm/hobbymac-sealed-test-r2 42, hobbylm/hobbymac-sealed-test-r3 14, hobbylm/hobbymac-sealed-test-r4 36, live_t1 111, route_v1 372 |
| v2new | route | 5596 | 5438 | external/hobbylm/sealed-r2 2, external/hobbylm/sealed-r3 2, external/hobbylm/sealed-r4 1, hobbylm/hobbymac-sealed-test 9, hobbylm/hobbymac-sealed-test-r2 1, hobbylm/hobbymac-sealed-test-r4 3, live_t1 60, route_v1 80 |
| v2new | args | 4262 | 4157 | external/hobbylm/sealed-r2 2, hobbylm/hobbymac-sealed-test 4, hobbylm/hobbymac-sealed-test-r2 1, hobbylm/hobbymac-sealed-test-r4 2, live_t1 58, route_v1 38 |
| ask2 | route | 78 | 77 | route_v1 1 |
| ask2 | args | 72 | 71 | route_v1 1 |

Independent check on the final `v2all` route/args files: 0 matches against the 570 external utterances.

## Other fixes

- G3 context pairs dropped: 1246 route items.
- Context constrained (copy_selection selection=yes, premiere_command app=Premiere Pro, type_text focused text field/area): {"premiere_command": 706, "type_text": 550, "copy_selection": 629}.
- ARGS dropped as ungrounded (string/path/contact values not in the utterance; case-insensitive, spoken numbers = digits, path separators/extensions split, quotes stripped): 1059. By skill: {"move_to_trash": 247, "compose_email": 138, "new_note": 110, "open_file": 109, "open_folder": 92, "create_reminder": 75, "send_message": 72, "web_search": 70, "play_music": 43, "advisor_prep": 25, "type_text": 21, "create_event": 21, "start_timer": 15, "find_file": 11, "new_folder": 9, "premiere_command": 1}.
- ASR noise: no longer applied to ARGS items (route items only).
- v2 relabel regex now matches catalog phrasings (lock my mac/computer/screen, clear out/empty the trash bin, bluetooth); items already labeled bluetooth/lock_screen/empty_trash are not re-scored.
- Final: 41904 route / 27936 ARGS before dedup.

## Examples of dropped ungrounded ARGS

- `start_timer` "Let the steak sit for about ten minutes before cutting." => `duration="about ten minutes" label="steak rest"`
- `move_to_trash` "Trash that CSV" => `path=/Users/alex/Downloads/usage_stats.csv`
- `start_timer` "Hands are gonna be under the sink for a full thirty seconds." => `duration="a full thirty seconds" label=handwashing`
- `open_file` "Open invoices.xlsx for accounting, thanks." => `path=~/Documents/invoices.xlsx`
- `advisor_prep` "What's my brief look like for the Sullivan review tomorrow?" => `client="the Sullivans"`
- `open_file` "Um, open my Calendar invite sprint-planning.ics." => `path=/Users/aria/Downloads/sprint-planning.ics`
- `create_reminder` "I keep forgetting my umbrella when it rains" => `title="bring an umbrella"`
- `new_note` "My sourdough starter needs feeding every twelve hours or so, don't let me forget." => `title=Sourdough body="feed starter every twelve hours"`
- `web_search` "search for, uh, jobs in Austin for product designers" => `query="product designer jobs in Austin"`
- `open_folder` "Need to see the budget spreadsheets, they're in the finance folder I think." => `path=~/Documents/Finance`
