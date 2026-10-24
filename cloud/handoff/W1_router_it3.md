# W1: Router iteration 3 (it3): finish, evaluate, export, deploy behind a flag

Repo `ardahk/muselet`. Read `docs/HANDOFF.md` §1–§4 and `AGENTS.md` (Decision API, Standing decisions) first.
You are taking over from the old org's training session "Cloud A". Its state is on branch `cloud/data-pipeline`
(PR #2) and in HF/Tinker.

## State at handoff (Sat 14:00 PDT)
- **Serving today:** it2 (`jonsnov/muselet-route-4b-main-mlx4` @ `54b21817`, tau .65). Clean route_v1 (103):
  .913 route acc, .857 end-to-end. Val top-1 .938, macro-F1 .931, ARGS exact about .869.
- **it3 plan** (approved by the lead):
  - catalog v3 (43 options = 39 skills + MULTI_STEP/ASK/REFUSE/ANSWER; draft_email and compose_text become
    routable) at `training/artifacts/catalog_v3.json`;
  - data = Cloud A's new-intent items + `jonsnov/muselet-route-datums-it3cand` @ `84595279452d9c43573012f78555e25376316cf8`
    (audit report: `training/data_route/REPORT.md`; residue notes: PR #31 `training/data_route/HANDOFF.md`);
  - 35B-teacher soft labels for every route item without one;
  - same recipe as it2 (LoRA r32, LR 4e-4, 1 epoch, batch 128, 60/40 route/ARGS, soft targets
    0.6·onehot + 0.4·teacher, 30% ASR noise).
- **Merge rules:** data-route's adjudicated labels win, then the v3 boundary relabel, then exact/near dedup; keep
  Cloud A's pinned val split.
- **Benchmark of record:** `evals/route_v2.jsonl` (955 items, sha256
  `20cd542b50862ccf4dc83af18cf16bb9b8c61ab5da505abf745d00aa3155dd51`, on branch `cloud/data-pipeline`), plus
  `evals/route_v1_clean.jsonl` (103).
- **Budget:** Tinker total must stay ≤ $140 (hard cap $150). It was $77.51 at 17:00Z Sat, and the decisions full
  run adds about $23. Check `python3 tools/tinker_spend.py`, or the Tinker console, before launching.

## Steps
1. Find out whether Cloud A already launched it3. Check its PR #2 commits and comments, the Tinker run list and
   the HF revisions of `jonsnov/muselet-route-4b-main-mlx4`.
   - **If it trained:** go to step 3.
   - **If not:** build the dataset exactly per the merge rules and launch. Post the exact cost estimate first,
     and stop if it would push the total past $140.
2. Training hygiene:
   - checkpoints every 200 steps;
   - keep all of them;
   - log val route top-1 / macro-F1 / ARGS exact at each.
3. **Evaluation, tuned vs tuned.**
   - Fit tau on val for each of it3, it2 and base.
   - Report route_v2 overall and per label, the subset of route_v2 whose gold label exists in the v2 catalog (it2
     can't emit draft_email or compose_text), route_v1_clean, ARGS exact on val, and ECE.
   - Use `evals/router_check.py` / Cloud A's eval scripts.
   - Pre-registered ship rule: it3 ships if route_v2 accuracy ≥ it2 + 2 points AND route_v1_clean ≥ it2 − 1
     point AND ARGS exact ≥ it2.
4. **Contamination gate:** `muselet_train.evalcheck.overlaps` against route_v1/v2, live_t1, HobbyLM sealed r1–r4,
   DeskMind diag/dyn/proposals. It must be **0** before any competitor benchmark uses it3.
5. **Export:**
   - MLX 4-bit with the **untied lm_head** (the r1 export tied it and broke ARGS; see `docs/REPORT.md`);
   - push a **new** HF revision and never overwrite it2's;
   - upload the val-fitted tau and `parity_300` (300 rendered prompts + expected top-1) for the Mac check.
6. **Serving integration** (PR to main):
   - a `ROUTER=it3` option in `tools/serve_brain.sh`, with its own tau;
   - `skills/catalog.json` switched to v3 *only when it3 is selected*, or both catalogs supported. Keep it2
     working;
   - regenerate `training/artifacts/route_render_samples.jsonl` so the route-parity tests pass for both.
7. **Mac check** (needs a Mac agent): load the MLX export, run parity_300 (top-1 agreement ≥ 0.99 with Tinker
   sampler logits), latency p50/p95.

## Acceptance
- Numbers table in the PR body, plus every HF revision and Tinker checkpoint id.
- Route parity tests green for it2 and it3.
- The it2 default unchanged until the lead flips it.

## Pitfalls
- Option ids shift in v3: the specials move to `f h i j`. Datums rendered with the v2 catalog put the specials on
  the wrong tokens.
- route_v2 is labelled under v3.
- Don't select checkpoints on route_v2 or JevBench (that's selecting on the eval). Use val.
