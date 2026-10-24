## Handoff

_Lane: router (System 1 route + ARGS LoRA on Qwen/Qwen3.5-4B via Tinker). Updated 2026-10-24 21:15Z._

**State**
- Done: catalog v3 (43 options, lead-approved; `training/artifacts/catalog_v3.json`, sha `fb99dd04…dd8cd20`); route_v2 frozen (`evals/route_v2.jsonl`, 955 items, sha256 `20cd542b50862ccf4dc83af18cf16bb9b8c61ab5da505abf745d00aa3155dd51`); it3 data = it3cand @ `84595279` merged with my new-intent data (`/data/gen/v3m`), 0 overlaps on all 4 gate rules; 35B teacher soft labels on 6,222 one-hot rows (applied, 0.6 gold + 0.4 teacher); base + it2 evals on route_v2 / route_v1 / v3 val + ARGS v3 val.
- In flight: Tinker training run `it3` (log `/data/train/logs/it3.log`, LR 4e-4, rank 32, 1 epoch, 496 steps, eval every 100). On finish it writes `/data/train/it3/{final_eval.json,checkpoints.json}` and `training/reports/phase1_it3.md`. Watcher `/data/train/after_it3.sh` (log `/data/train/logs/after_it3.log`) then runs the it3 evals (`eval_it3.log`) and the export (`post_it3.sh` → `post_it3.log`: parity_300_it3, download, untied merge, MLX 4-bit, render check).
- Not done: tau report for it3, HF upload, PR/lead post.

**Next steps (exact)**
1. `cd training; export MUSELET_CATALOG=$PWD/artifacts/catalog_v3.json`
2. When `after_it3.log` prints AFTER_DONE: `uv run python -m muselet_train.tau --names base_v3 it2_v3eval it3 --val-tag val3 --out reports/it3_route_v2.json` (rule = evals/router_check.py: p_top<tau → MULTI_STEP, max val macro-F1, ties acc then lower tau, TAUS grid).
3. Ship rule (pre-registered): route_v2 tuned ≥ it2 + 2 pts, route_v1_clean ≥ it2 − 1, ARGS exact (runtime) ≥ it2. it2 numbers: `/data/train/tau_mac_pre.json`, `/data/train/it2_v3eval/eval_args_val3.json`.
4. Copy into `/data/export/it3/mlx-4bit/`: `tau.json` (it3 fitted tau + grid), `parity_300.jsonl` (= artifacts/parity_300_it3.jsonl), `route_render_samples_v3.jsonl`, `catalog_v3.json`. Verify `config.json` has `tie_word_embeddings=false` (root + text_config) and a separate `lm_head`.
5. Upload: `uv run python -m muselet_train.export upload --dir /data/export/it3/mlx-4bit --repo jonsnov/muselet-route-4b-main-mlx4` → new revision (never overwrite it2 `54b21817…`).
6. Post to lead: revision, tau, three-way table (base/it2/it3; route_v2 all + v2-label subset + route_v1_clean; accepted precision, handoff, argmax), per-label route_v2, ARGS val.

**Artifacts**
- Branch `cloud/data-pipeline`, [PR #2](https://github.com/ardahk/muselet/pull/2); latest commits f6354d6 (merge/teacher/v3 samples/eval), 34aff30 (tau).
- HF: models `jonsnov/muselet-route-4b-main-mlx4` (r2 `2e3e7bf`, it2 `54b21817ba9a22753cb487ad1deea6d696bc2c73`); datums `jonsnov/muselet-route-datums-it2` @ `aa0e4095…`, `…-it2b` @ `8df540b`, `…-it3cand` @ `84595279452d9c43573012f78555e25376316cf8`.
- Tinker: it2 `tinker://73495408-9d6d-56b5-9e1a-894744c13add:train:0/sampler_weights/it2-final`; it3 paths will be in `/data/train/it3/checkpoints.json` (it3-200, it3-400 state, it3-final sampler + state). Keep every checkpoint.
- Run dirs: `/data/gen/v3m` (merged pool, teacher_in/teacher_v3, val_items.jsonl), `/data/train/{base_v3,it2_v3eval,it3}` (pred_*.jsonl, eval_*.json), `/data/export/it3`.

**Spend**
- Tinker: $77.51 through 17:00Z (lead) + decisions run ~$23 + it3 teacher $3.91 + it3 training est $31.61 + evals ~$2 ≈ $138. Stop line $140, hard cap $150.
- OpenAI/Anthropic (this lane): ~$15 (route_v2 + it3 gen + v3 relabel).

**Open questions for the lead**
- None blocking. it2's Mac tau (.65) was fit on its own dev rows; here it2 is refit on the v3 val (1,396) with its v2 option list (tau .50).

**Gotchas**
- Always set `MUSELET_CATALOG=training/artifacts/catalog_v3.json` for it3 (renderer, datums, evals); unset it (= `skills/catalog.json`, v2, 41 options) for it2. Option ids skip `a c g`: `b=advisor_prep d=draft_email e=compose_text f=MULTI_STEP h=ASK i=REFUSE j=ANSWER`.
- `teacher.py` needs `--cap 140 --phase1-spent <spent>` or its Phase-1 guard aborts.
- route_v1 gold labels are v2-era; route_v1_clean = indices `route_v1_clean_both` in `training/reports/evalcheck/clean_subsets.json`.
- Large data lives on `/data` (not in git). Secrets only via env (TINKER_API_KEY, HF_TOKEN, OPENAI_API_KEY, ANTHROPIC_API_KEY).
