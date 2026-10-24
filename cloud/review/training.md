
## Your lane: `training` — router data, labels and Tinker training
Files: everything on `cloud/data-pipeline` (PR #2) plus `training/SPEC.md`, `training/cloud_kickoff.md`,
`skills/catalog.json`, `training/artifacts/`, `training/recon/`, `training/reports/`.
The spec is the lead's; the cloud worker implements it. Decisions the lead already made (do not re-litigate):
1 epoch for the main run (second epoch decided later from eval curves), Phase 1 cap $60, hard total $150;
tinker-cookbook 0.5.8 pin is an approved exception; ASK near-miss prompt text was changed for ASK only;
for ASK items on skills with 2+ required args, missing = first required arg (catalog order) the ARGS labeler
did not extract; license-unclear datasets (go-browse-wa, Mind2Web-axtree) excluded; HF uploads go to private
repos under `jonsnov/`.
Look hardest at:
- Implementation vs `training/SPEC.md`: exact prompt texts, label set, soft-label construction (teacher
  probabilities mixed with the intended label as specified), noise injection, adjudication, quotas.
- Eval hygiene: dedup/near-dup filtering against `evals/route_v1.jsonl` and every eval set listed in
  `AGENTS.md`; leakage through templates, paraphrase or shared seeds; split integrity (no utterance family in
  both train and val). Any leak is P0.
- Label quality: sample the generated data yourself (read 30+ items per label from what is committed) and
  report systematic mislabels with counts.
- Renderer/token parity: route datums must be byte-identical to what the Mac runtime renders (renderer
  `qwen3_5`, empty think block, 58-id alphabet, `choice#` prefix [11409, 2]); check the parity/export plan
  (MLX conversion, 300-example agreement test) for gaps.
- Spend: recompute token counts × price ($0.737/M for Qwen3.5-4B training as quoted) for every planned run;
  flag anything that could cross $60 (phase) or $150 (total), including teacher sampling and retries.
- Training config: LR sweep, batch mixing of route/args datums, metrics (top-1, macro-F1, ECE, Brier,
  per-label, ARGS exact match), checkpoint selection by val not test.
