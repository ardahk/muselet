# Phase 1 run `pilot-lr2e-4`

```json
{
 "run": "v2all",
 "name": "pilot-lr2e-4",
 "teacher_files": [
  "teacher_pilot_adj.jsonl"
 ],
 "model": "Qwen/Qwen3.5-4B",
 "limit": 4000,
 "lr": 0.0002,
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
| 31 | 0.3158 | 0.853 | 0.838 | 0.045 | 0.202 | 0.740 |

Per-label val accuracy (last eval):

| label | acc |
|---|---|
| ANSWER | 0.957 |
| MULTI_STEP | 0.706 |
| REFUSE | 0.964 |
| advisor_prep | 1.000 |
| battery_status | 1.000 |
| bluetooth | 1.000 |
| change_volume | 0.600 |
| compose_email | 0.625 |
| copy_selection | 1.000 |
| create_event | 1.000 |
| create_reminder | 1.000 |
| dark_mode | 0.250 |
| empty_trash | 1.000 |
| finance_review | 0.000 |
| find_file | 0.750 |
| hide_app | 1.000 |
| lock_screen | 0.667 |
| media_control | 1.000 |
| move_to_trash | 0.667 |
| mute | 1.000 |
| new_folder | 1.000 |
| new_note | 0.857 |
| open_app | 1.000 |
| open_file | 1.000 |
| open_folder | 0.800 |
| open_url | 1.000 |
| play_music | 0.800 |
| premiere_command | 0.667 |
| quit_app | 1.000 |
| send_message | 1.000 |
| set_brightness | 1.000 |
| set_volume | 0.714 |
| sleep_display | 1.000 |
| start_timer | 1.000 |
| take_screenshot | 0.667 |
| todays_agenda | 1.000 |
| type_text | 1.000 |
| web_search | 0.500 |
| wifi | 1.000 |
| window_layout | 0.500 |

Checkpoints:

- step 31: `tinker://37cce29d-abfe-5c5a-9115-47490c6d1b2a:train:0/sampler_weights/pilot-lr2e-4-final`
- step 31: `tinker://37cce29d-abfe-5c5a-9115-47490c6d1b2a:train:0/weights/pilot-lr2e-4-final`
