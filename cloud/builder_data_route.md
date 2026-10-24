# Cloud builder: data-route (router + ARGS training-data quality for iteration 3) — Muselet

Repo `ardahk/muselet`. Read `AGENTS.md`, `training/SPEC.md` and PR #2's `training/reports/` (phase1_main.md,
phase1_it2.md, evalcheck/). Cloud A (session 25d3d0c1) owns training and the pipeline code on `cloud/data-pipeline`.
You produce better DATA plus an audit, and hand them to cloud A through the lead; you never start Tinker runs. Branch
`cloud/data-route` (new files under `training/data_route/` only), one PR.

Goal: the cleanest, most diverse route+ARGS pool for it3. it2 val top-1 is .938; weak labels are compose_email .72,
media_control .80, open_folder .80, set_brightness .81. New intents need data:
- messaging to named people;
- draft_email / compose_text (hidden skills, see `skills/catalog.json` once brain-7 / comms merge);
- bare site names ("go to wikipedia", gmail = website);
- writing content.

1. **Audit it2's pool** (`jonsnov/muselet-route-datums-it2b` @ 8df540b). Sample 1,500 items stratified by label.
   - Two independent frontier judges (one OpenAI, one Anthropic) label each with the catalog plus context. Where they
     disagree with the gold or with each other, a third adjudicates.
   - Report the noise rate per label with examples, and fix or drop by rule. Never silently.
2. **Targeted generation** for weak labels and new intents.
   - Hard-negative pairs (compose_email vs send_message vs draft_email; media_control vs premiere_command;
     open_folder vs open_file vs find_file; set_brightness vs dark_mode vs change_volume).
   - Realistic ASR noise (fillers, restarts, homophones, missing punctuation) and context diversity (frontmost app,
     focused element, selection).
   - Grounded ARGS: every ARGS value must appear in the utterance, or follow from it by the documented coercions.
3. **Decontamination gate** (cloud A's evalcheck rules: normalized exact, 13-gram, token edit ≤ 1 for short items,
   CJK-aware) against route_v1, live_t1, evals/external, HobbyLM r1–r4, DeskMind diag/dyn, and route_v2 once cloud A
   freezes it. Result must be 0 on every rule.
4. **Deliver:**
   - a private HF dataset `jonsnov/muselet-route-datums-it3cand`, in the same datum format as it2b;
   - `training/data_route/REPORT.md` with counts per label, noise found and fixed, and the gate results.
   Budget: up to $80 total API (OpenAI + Anthropic); report the spend.
Reply after the audit (step 1) with the noise numbers, then again at delivery.
