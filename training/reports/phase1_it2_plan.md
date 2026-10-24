# Phase 1 iteration 2: hypotheses (written before launch)

Fresh run, same settings as `main` (Qwen3.5-4B, LoRA r32, Adam, LR 4e-4, 1 epoch, mixed 60/40, batch 128), so the
comparison isolates the data change. Data run `v2it2` = full1 + v2new + it2 top-ups + all ask2 ASK items, via the
fixed reader (route_train/route_val; no G3; constrained contexts).

Data changes:
1. Reader fix: G3 dropped and contexts constrained (premiere_command -> Premiere Pro, copy_selection -> selection,
   type_text -> text field). In `main` these fixes were missing from route data (stale `route_dedup.jsonl`).
2. ASK by rule (`ask_rule.py`): ASK only when the ARGS labeler finds a required argument missing and the request
   names no value for it; otherwise relabel to `nearest_skill`. One-hot targets. Replaces Sonnet agreement.
3. finance_review strict check (`finance_check.py`): A1's MULTI_STEP -> finance_review relabels are kept only for
   categorize / duplicates / receipts / over_budget; the rest go back to MULTI_STEP (one-hot).
4. Top-ups (`gen build_it2`, 111 sync calls): indirect dark_mode with set_brightness / sleep_display contrast,
   open_app verb paraphrases, find_file vs open_file, create_reminder vs create_event, generic media_control
   playback vs Premiere timeline playback, polite-complete requests for every skill with a required argument
   (ASK hard negatives), and terse missing-argument ASK.

Before = `main` (sampler_weights/main-final). Val numbers are compared on the same split: main-final is re-scored
on the v2it2 val split, because the split changed.

| # | Hypothesis | Confirmed if |
|---|---|---|
| H1 | Constrained contexts + playback top-up fix media_control -> premiere_command | media_control val acc >= 0.85; <= 1 media_control->premiere_command val error; every route_v1 media_control item correct |
| H2 | Rule-validated + terse ASK teaches missing-argument ASK without eating complete requests | route_v1 ASK >= 6/8; val ASK acc >= 0.70; route_v1 non-ASK items predicted ASK <= 2 |
| H3 | Strict finance check removes generic spreadsheet work from finance_review | MULTI_STEP->finance_review val errors <= 1% of MULTI_STEP val; 0 route_v1 MULTI_STEP items predicted finance_review; finance_review val acc >= 0.90 and route_v1 finance_review items correct |
| H4 | Indirect dark_mode coverage + contrast fixes dark_mode -> sleep_display/set_brightness | dark_mode val acc >= 0.85; <= 1 dark_mode->sleep_display val error |
| H5 | open_app verb paraphrases fix open_app -> MULTI_STEP | every route_v1 open_app item correct |
| H6 | find_file/open_file and create_reminder/create_event contrasts help both | find_file and create_reminder val acc >= 0.85 |
| H7 | Control: set_volume / change_volume data unchanged | both >= 0.85 val acc (no regression) |
| H8 | Overall | val top-1 > main-final on the same split; route_v1 top-1 >= 0.90; ECE <= 0.03; ARGS EM >= 0.87 |
