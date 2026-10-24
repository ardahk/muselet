# evals-safety digest, pass 1 (2026-10-24T05:17:27Z)

## Open P0/P1 (ranked)
1. evals-safety-1 P0: route_v1 eval set leaks into router training data and prompts (training/artifacts/gen_sample2_picked.jsonl, training/src/muselet_train/prompts.py)
2. evals-safety-2 P0: script confirm regex misses rm -rf, doShellScript, Terminal do script (ml/src/brain/orchestrator.py)
3. evals-safety-5 P1: confirmed=true arg skips confirm; confirm text omits recipient/body (ml/src/brain/catalog.py, orchestrator.py)
4. evals-safety-3 P1: eval-route args_exact compares raw strings to typed labels (ml/src/brain/cli.py)
5. evals-safety-4 P1: eval-route ignores case ctx.online and confirm-threshold gating (ml/src/brain/decision.py, cli.py)
6. evals-safety-6 P1: irreversible UI acts rely only on planner; injection via observations (prompts/planner_system.md, orchestrator.py)

Checked and clean: every finance answer key recomputed independently with Decimal (all match; regeneration byte-identical). Full-blob secret scan over every commit on all branches found no secret-like strings. .gitignore covers .env, models/, data/, runs/. Premiere bridge connects only to ws://127.0.0.1:8766 and dispatches only named commands (no eval/exec). Its export_sequence writes to any output_path without confirm (low risk). Premiere docs corpus scraped 0 pages (stats.json).

## Highest-leverage next moves
- Before any Tinker route run: add eval dedup (normalized exact + char-5-gram/bigram Jaccard) and remove eval items from the generator few-shots. Otherwise route_v1 numbers are not reportable.
- Make eval-route score the production path (coerce + validate args, ctx.online, tau gating), and report wrong_action_rate next to accuracy.
- Replace the script blocklist with an allowlist, add an observation-is-data rule to the planner, and add a brain-side confirm for send/delete/buy presses.
- No end-to-end task harness exists yet (speed_lab measures prefill/decode only). Build one that judges success by final AX/file state (finance: read the Numbers cells back and diff against budget_oct2026.truth.json) and logs per-stage latency, then run HobbyLM and DeskMind on the same task list on this machine.
- Finance fixtures: lead decision on budgets (5/8 over budget), plus a weekend key and grading rules in README.
