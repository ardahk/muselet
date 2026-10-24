# Phase 1 run `main`

```json
{
 "run": "v2all",
 "name": "main",
 "teacher_files": [
  "teacher_pilot_adj.jsonl",
  "teacher_ask_adj.jsonl",
  "teacher_v2_adj.jsonl"
 ],
 "model": "Qwen/Qwen3.5-4B",
 "limit": 0,
 "lr": 0.0004,
 "epochs": 1,
 "batch": 128,
 "rank": 32,
 "route_frac": 0.6,
 "mode": "mixed",
 "eval_every": 50,
 "save_every": 200,
 "val_route": 300,
 "val_args": 200,
 "max_usd": 35.0,
 "seed": 0,
 "final_full_val": true,
 "dry_run": false,
 "train_route": 36580,
 "train_args": 27023,
 "steps": 496,
 "train_tokens": 37591451,
 "eval_tokens": 6079211,
 "est_usd": 29.45
}
```

| step | train loss | val top1 | macro-F1 | ECE | Brier | ARGS EM |
|---|---|---|---|---|---|---|
| 50 | 0.2603 | 0.907 | 0.882 | 0.035 | 0.141 | 0.760 |
| 100 | 0.1385 | 0.923 | 0.889 | 0.037 | 0.123 | 0.790 |
| 150 | 0.2666 | 0.893 | 0.858 | 0.042 | 0.166 | 0.805 |
| 200 | 0.2885 | 0.913 | 0.884 | 0.051 | 0.139 | 0.790 |
| 250 | 0.3065 | 0.907 | 0.890 | 0.025 | 0.138 | 0.800 |
| 300 | 0.1542 | 0.923 | 0.899 | 0.042 | 0.134 | 0.810 |
| 350 | 0.1925 | 0.913 | 0.875 | 0.028 | 0.125 | 0.800 |
| 400 | 0.2363 | 0.893 | 0.856 | 0.042 | 0.154 | 0.785 |
| 450 | 0.1477 | 0.903 | 0.872 | 0.037 | 0.137 | 0.805 |
| 475 | 0.2674 | 0.910 | 0.878 | 0.031 | 0.145 | 0.820 |

Final eval on the full val split (1130 route, 792 ARGS): top1 0.918, macro-F1 0.885, ECE 0.016, Brier 0.125, ARGS EM 0.869

Per-label val accuracy (full val split; n = val items):

| label | acc | n |
|---|---|---|
| ANSWER | 0.973 | 110 |
| ASK | 0.000 | 3 |
| MULTI_STEP | 0.882 | 152 |
| REFUSE | 0.970 | 67 |
| advisor_prep | 1.000 | 24 |
| battery_status | 1.000 | 20 |
| bluetooth | 1.000 | 20 |
| change_volume | 0.909 | 22 |
| compose_email | 0.833 | 24 |
| copy_selection | 1.000 | 19 |
| create_event | 1.000 | 24 |
| create_reminder | 0.792 | 24 |
| dark_mode | 0.684 | 19 |
| empty_trash | 1.000 | 23 |
| finance_review | 1.000 | 36 |
| find_file | 0.708 | 24 |
| hide_app | 0.867 | 15 |
| lock_screen | 1.000 | 20 |
| media_control | 0.316 | 19 |
| move_to_trash | 0.962 | 26 |
| mute | 0.895 | 19 |
| new_folder | 1.000 | 20 |
| new_note | 0.800 | 25 |
| open_app | 1.000 | 18 |
| open_file | 0.913 | 23 |
| open_folder | 0.900 | 20 |
| open_url | 1.000 | 22 |
| play_music | 1.000 | 21 |
| premiere_command | 0.950 | 20 |
| quit_app | 1.000 | 17 |
| send_message | 0.958 | 24 |
| set_brightness | 0.905 | 21 |
| set_volume | 0.857 | 21 |
| sleep_display | 1.000 | 20 |
| start_timer | 1.000 | 23 |
| take_screenshot | 0.857 | 21 |
| todays_agenda | 1.000 | 21 |
| type_text | 0.952 | 21 |
| web_search | 0.818 | 22 |
| wifi | 0.950 | 20 |
| window_layout | 1.000 | 20 |

Data:

```json
{
 "ask_dropped": {
  "ASK": 184
 },
 "relabeled": {
  "MULTI_STEP->finance_review": 358,
  "MULTI_STEP->find_file": 3,
  "MULTI_STEP->type_text": 1,
  "MULTI_STEP->take_screenshot": 5,
  "MULTI_STEP->quit_app": 1,
  "MULTI_STEP->new_note": 2,
  "MULTI_STEP->create_event": 1,
  "MULTI_STEP->change_volume": 2,
  "MULTI_STEP->ANSWER": 6,
  "new_folder->open_folder": 2,
  "premiere_command->ASK": 3,
  "open_url->ASK": 1,
  "MULTI_STEP->empty_trash": 1,
  "MULTI_STEP->lock_screen": 2,
  "MULTI_STEP->ASK": 4,
  "MULTI_STEP->web_search": 1,
  "MULTI_STEP->create_reminder": 5,
  "change_volume->set_volume": 2,
  "open_folder->find_file": 1,
  "type_text->new_note": 1,
  "REFUSE->MULTI_STEP": 12,
  "premiere_command->media_control": 2,
  "create_event->ASK": 1,
  "MULTI_STEP->premiere_command": 2,
  "REFUSE->empty_trash": 9,
  "MULTI_STEP->send_message": 1,
  "sleep_display->ASK": 1,
  "MULTI_STEP->start_timer": 1,
  "take_screenshot->ASK": 1,
  "open_folder->ASK": 1,
  "media_control->change_volume": 1,
  "move_to_trash->window_layout": 1,
  "set_volume->mute": 1,
  "compose_email->send_message": 1,
  "REFUSE->lock_screen": 10,
  "REFUSE->bluetooth": 1,
  "REFUSE->finance_review": 1,
  "REFUSE->compose_email": 1,
  "ANSWER->lock_screen": 1,
  "ANSWER->empty_trash": 1
 },
 "dropped": {
  "MULTI_STEP": 660,
  "REFUSE": 28
 },
 "route_by_label": {
  "MULTI_STEP": 5113,
  "ANSWER": 3674,
  "REFUSE": 2295,
  "finance_review": 1122,
  "web_search": 834,
  "move_to_trash": 815,
  "create_event": 810,
  "compose_email": 808,
  "send_message": 805,
  "new_note": 804,
  "create_reminder": 793,
  "advisor_prep": 786,
  "find_file": 780,
  "open_file": 752,
  "empty_trash": 751,
  "start_timer": 743,
  "change_volume": 742,
  "open_url": 741,
  "type_text": 727,
  "new_folder": 709,
  "set_volume": 708,
  "todays_agenda": 702,
  "lock_screen": 697,
  "set_brightness": 692,
  "window_layout": 690,
  "play_music": 682,
  "open_folder": 663,
  "take_screenshot": 661,
  "battery_status": 655,
  "premiere_command": 654,
  "bluetooth": 653,
  "wifi": 635,
  "sleep_display": 632,
  "copy_selection": 630,
  "mute": 629,
  "open_app": 625,
  "media_control": 615,
  "dark_mode": 583,
  "quit_app": 582,
  "hide_app": 524,
  "ASK": 194
 },
 "args_dropped_with_route": 872
}
```

Checkpoints:

- step 200: `tinker://22569d87-0b83-5249-9854-ecf447cca10d:train:0/weights/main-200`
- step 400: `tinker://22569d87-0b83-5249-9854-ecf447cca10d:train:0/weights/main-400`
- step 475: `tinker://22569d87-0b83-5249-9854-ecf447cca10d:train:0/sampler_weights/main-final`
- step 475: `tinker://22569d87-0b83-5249-9854-ecf447cca10d:train:0/weights/main-final`
