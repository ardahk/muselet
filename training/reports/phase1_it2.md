# Phase 1 run `it2`

```json
{
 "run": "v2it2",
 "name": "it2",
 "teacher_files": [
  "teacher_pilot_adj.jsonl",
  "teacher_ask_adj.jsonl",
  "teacher_v2_adj.jsonl"
 ],
 "model": "Qwen/Qwen3.5-4B",
 "limit": 63603,
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
 "train_route": 38162,
 "train_args": 25441,
 "steps": 496,
 "train_tokens": 38884306,
 "eval_tokens": 6215716,
 "est_usd": 30.44
}
```

| step | train loss | val top1 | macro-F1 | ECE | Brier | ARGS EM | ARGS EM runtime | ARGS empty runtime |
|---|---|---|---|---|---|---|---|---|
| 50 | 0.2963 | 0.943 | 0.932 | 0.065 | 0.119 | 0.510 | 0.800 | 0.155 |
| 100 | 0.1868 | 0.903 | 0.890 | 0.049 | 0.151 | 0.655 | 0.765 | 0.160 |
| 150 | 0.2837 | 0.930 | 0.933 | 0.035 | 0.111 | 0.815 | 0.835 | 0.160 |
| 200 | 0.2604 | 0.890 | 0.881 | 0.045 | 0.164 | 0.845 | 0.840 | 0.160 |
| 250 | 0.2806 | 0.923 | 0.915 | 0.026 | 0.113 | 0.820 | 0.815 | 0.160 |
| 300 | 0.1330 | 0.923 | 0.917 | 0.033 | 0.108 | 0.835 | 0.840 | 0.155 |
| 350 | 0.3521 | 0.950 | 0.941 | 0.031 | 0.089 | 0.810 | 0.815 | 0.160 |
| 400 | 0.2874 | 0.913 | 0.902 | 0.042 | 0.127 | 0.835 | 0.835 | 0.155 |
| 450 | 0.1597 | 0.903 | 0.893 | 0.041 | 0.130 | 0.805 | 0.820 | 0.160 |
| 495 | 0.1751 | 0.937 | 0.923 | 0.029 | 0.099 | 0.860 | 0.860 | 0.155 |

Final eval on the full val split (1216 route, 878 ARGS): top1 0.938, macro-F1 0.931, ECE 0.021, Brier 0.097, ARGS EM 0.866, ARGS EM with the runtime rendering (gate) 0.869, empty 0.156

Per-label val accuracy (full val split; n = val items):

| label | acc | n |
|---|---|---|
| ANSWER | 0.963 | 109 |
| ASK | 0.917 | 12 |
| MULTI_STEP | 0.918 | 159 |
| REFUSE | 0.985 | 66 |
| advisor_prep | 1.000 | 25 |
| battery_status | 0.950 | 20 |
| bluetooth | 1.000 | 21 |
| change_volume | 0.870 | 23 |
| compose_email | 0.720 | 25 |
| copy_selection | 1.000 | 19 |
| create_event | 1.000 | 29 |
| create_reminder | 0.939 | 33 |
| dark_mode | 0.893 | 28 |
| empty_trash | 0.958 | 24 |
| finance_review | 1.000 | 30 |
| find_file | 0.971 | 34 |
| hide_app | 1.000 | 15 |
| lock_screen | 0.955 | 22 |
| media_control | 0.800 | 25 |
| move_to_trash | 1.000 | 25 |
| mute | 0.842 | 19 |
| new_folder | 1.000 | 22 |
| new_note | 0.880 | 25 |
| open_app | 1.000 | 27 |
| open_file | 0.852 | 27 |
| open_folder | 0.800 | 20 |
| open_url | 1.000 | 19 |
| play_music | 0.909 | 22 |
| premiere_command | 0.957 | 23 |
| quit_app | 1.000 | 19 |
| send_message | 1.000 | 25 |
| set_brightness | 0.808 | 26 |
| set_volume | 0.810 | 21 |
| sleep_display | 0.870 | 23 |
| start_timer | 1.000 | 23 |
| take_screenshot | 0.905 | 21 |
| todays_agenda | 1.000 | 21 |
| type_text | 1.000 | 22 |
| web_search | 0.960 | 25 |
| wifi | 0.950 | 20 |
| window_layout | 1.000 | 22 |

Data:

```json
{
 "ask_dropped": {
  "ASK": 30
 },
 "relabeled": {
  "MULTI_STEP->finance_review": 111,
  "MULTI_STEP->find_file": 3,
  "MULTI_STEP->type_text": 1,
  "MULTI_STEP->take_screenshot": 5,
  "MULTI_STEP->quit_app": 1,
  "MULTI_STEP->new_note": 2,
  "MULTI_STEP->create_event": 1,
  "MULTI_STEP->change_volume": 2,
  "MULTI_STEP->ANSWER": 6,
  "new_folder->open_folder": 2,
  "open_url->ASK": 1,
  "MULTI_STEP->empty_trash": 1,
  "MULTI_STEP->ASK": 4,
  "MULTI_STEP->web_search": 1,
  "MULTI_STEP->create_reminder": 5,
  "change_volume->set_volume": 2,
  "open_folder->find_file": 1,
  "REFUSE->MULTI_STEP": 12,
  "create_event->ASK": 1,
  "MULTI_STEP->premiere_command": 2,
  "REFUSE->empty_trash": 9,
  "MULTI_STEP->send_message": 1,
  "sleep_display->ASK": 1,
  "MULTI_STEP->start_timer": 1,
  "take_screenshot->ASK": 1,
  "set_volume->mute": 1,
  "compose_email->send_message": 1,
  "ASK->mute": 7,
  "ASK->set_brightness": 2,
  "ASK->dark_mode": 7,
  "ASK->wifi": 12,
  "ASK->sleep_display": 7,
  "ASK->battery_status": 3,
  "ASK->find_file": 17,
  "ASK->take_screenshot": 9,
  "ASK->start_timer": 2,
  "ASK->todays_agenda": 9,
  "ASK->new_note": 1,
  "ASK->play_music": 7,
  "ASK->media_control": 4,
  "ASK->bluetooth": 11,
  "ASK->empty_trash": 23,
  "ASK->change_volume": 2,
  "ASK->premiere_command": 17,
  "ASK->quit_app": 16,
  "ASK->hide_app": 6,
  "ASK->open_app": 9,
  "ASK->finance_review": 68,
  "ASK->copy_selection": 7,
  "ASK->window_layout": 10,
  "ASK->create_event": 4,
  "ASK->advisor_prep": 2,
  "ASK->create_reminder": 6,
  "REFUSE->lock_screen": 10,
  "REFUSE->bluetooth": 1,
  "REFUSE->finance_review": 1,
  "REFUSE->compose_email": 1,
  "ANSWER->lock_screen": 1,
  "ASK->lock_screen": 4,
  "ASK->type_text": 1,
  "ASK->open_file": 1,
  "ASK->set_volume": 5,
  "ASK->web_search": 2,
  "ANSWER->empty_trash": 1
 },
 "dropped": {
  "MULTI_STEP": 660,
  "REFUSE": 28
 },
 "finance_reverted": {
  "MULTI_STEP": 247
 },
 "route_by_label": {
  "MULTI_STEP": 5349,
  "ANSWER": 3661,
  "REFUSE": 2246,
  "find_file": 1114,
  "create_reminder": 1036,
  "create_event": 980,
  "dark_mode": 949,
  "finance_review": 943,
  "open_file": 913,
  "open_app": 893,
  "set_brightness": 856,
  "web_search": 836,
  "media_control": 834,
  "send_message": 832,
  "move_to_trash": 830,
  "new_note": 828,
  "compose_email": 827,
  "advisor_prep": 827,
  "empty_trash": 774,
  "premiere_command": 772,
  "start_timer": 768,
  "change_volume": 762,
  "sleep_display": 759,
  "type_text": 741,
  "new_folder": 740,
  "window_layout": 724,
  "set_volume": 722,
  "play_music": 716,
  "todays_agenda": 703,
  "bluetooth": 690,
  "lock_screen": 686,
  "wifi": 679,
  "battery_status": 653,
  "mute": 651,
  "take_screenshot": 647,
  "open_url": 636,
  "open_folder": 622,
  "copy_selection": 622,
  "quit_app": 603,
  "hide_app": 522,
  "ASK": 451
 },
 "args_dropped_with_route": 718
}
```

Checkpoints:

- step 200: `tinker://73495408-9d6d-56b5-9e1a-894744c13add:train:0/weights/it2-200`
- step 400: `tinker://73495408-9d6d-56b5-9e1a-894744c13add:train:0/weights/it2-400`
- step 495: `tinker://73495408-9d6d-56b5-9e1a-894744c13add:train:0/sampler_weights/it2-final`
- step 495: `tinker://73495408-9d6d-56b5-9e1a-894744c13add:train:0/weights/it2-final`
