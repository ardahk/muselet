# Phase 1 run `pilot-lr4e-4`

```json
{
 "run": "v2all",
 "name": "pilot-lr4e-4",
 "teacher_files": [
  "teacher_pilot_adj.jsonl"
 ],
 "model": "Qwen/Qwen3.5-4B",
 "limit": 4000,
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
 "max_usd": 8.0,
 "seed": 0,
 "dry_run": false,
 "train_route": 2400,
 "train_args": 1600,
 "steps": 31,
 "train_tokens": 2444167,
 "eval_tokens": 441368,
 "est_usd": 1.93
}
```

| step | train loss | val top1 | macro-F1 | ECE | Brier | ARGS EM |
|---|---|---|---|---|---|---|
| 31 | 0.2773 | 0.880 | 0.877 | 0.046 | 0.173 | 0.740 |

Per-label val accuracy (last eval):

| label | acc |
|---|---|
| ANSWER | 0.957 |
| MULTI_STEP | 0.843 |
| REFUSE | 0.893 |
| advisor_prep | 1.000 |
| battery_status | 1.000 |
| bluetooth | 1.000 |
| change_volume | 0.600 |
| compose_email | 0.625 |
| copy_selection | 1.000 |
| create_event | 1.000 |
| create_reminder | 1.000 |
| dark_mode | 0.500 |
| empty_trash | 1.000 |
| finance_review | 0.250 |
| find_file | 0.750 |
| hide_app | 1.000 |
| lock_screen | 1.000 |
| media_control | 1.000 |
| move_to_trash | 0.667 |
| mute | 1.000 |
| new_folder | 1.000 |
| new_note | 0.714 |
| open_app | 0.800 |
| open_file | 1.000 |
| open_folder | 0.800 |
| open_url | 1.000 |
| play_music | 0.800 |
| premiere_command | 0.833 |
| quit_app | 0.800 |
| send_message | 0.857 |
| set_brightness | 1.000 |
| set_volume | 0.857 |
| sleep_display | 1.000 |
| start_timer | 0.833 |
| take_screenshot | 1.000 |
| todays_agenda | 1.000 |
| type_text | 1.000 |
| web_search | 0.750 |
| wifi | 1.000 |
| window_layout | 1.000 |

Checkpoints:

- step 31: `tinker://bf5fedb0-9fd9-5ad5-97b6-10bf0dff1af0:train:0/sampler_weights/pilot-lr4e-4-final`
- step 31: `tinker://bf5fedb0-9fd9-5ad5-97b6-10bf0dff1af0:train:0/weights/pilot-lr4e-4-final`
