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

Selection rule (evals-safety-27): every hypothesis and every checkpoint choice is judged on route_val (the
held-out val split) only. The it2 val split is pinned to main's split (`dedup --pin-split-from`): items main held
out stay in val, so main-final and it2 are compared on the same held-out items. route_v1 is reported once, at the
end, as the final number, flagged "not used for selection".

Style notes in the top-up prompts are written from the catalog definitions; they quote no eval wording (decisions-9).
Decontam additionally drops items of <= 5 tokens within token edit distance 1 of any eval utterance.

| # | Hypothesis | Confirmed if (route_val, same split for main-final and it2) |
|---|---|---|
| H1 | Constrained contexts + playback top-up fix media_control -> premiere_command | media_control val acc >= 0.85; <= 1 media_control->premiere_command error |
| H2 | Rule-validated ASK teaches missing-argument ASK without eating complete requests | ASK val acc >= 0.70; non-ASK val items predicted ASK <= 1% of val |
| H3 | Strict finance check removes generic spreadsheet work from finance_review | MULTI_STEP->finance_review errors <= 1% of MULTI_STEP val; finance_review val acc >= 0.90 |
| H4 | Indirect dark_mode coverage + contrast fixes dark_mode -> sleep_display/set_brightness | dark_mode val acc >= 0.85; <= 1 dark_mode->sleep_display error |
| H5 | open_app verb variety fixes open_app -> MULTI_STEP | open_app val acc >= 0.95; <= 1 open_app->MULTI_STEP error |
| H6 | find_file/open_file and create_reminder/create_event contrasts help both | find_file and create_reminder val acc >= 0.85 |
| H7 | Control: set_volume / change_volume data unchanged | both >= 0.85 val acc (no regression) |
| H8 | Overall | val top-1 > main-final; val ECE <= 0.03; ARGS EM >= 0.87 |
