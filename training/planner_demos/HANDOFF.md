## Handoff

**State:** step 2 (teacher demonstrations) is done and waiting for lead review in PR #33 (branch `cloud/planner-demos`).
- Done:
  - 1,496 states validated and gated, then answered by both teachers.
  - 1,194 demos and a 1,194-entry retrieval bank uploaded.
  - Report at `training/planner_demos/REPORT.md`.
- In flight: nothing. No processes are running; PR #33 has no CI checks configured.
- Step 1 (benchmark v2) was merged earlier in PR #29.

**Next steps (only once the lead decides):**
1. Permission-prompt demos are thin (26/135 kept). The lead picks one of two options:
   - (a) a code gate in the orchestrator, per `cloud/builder_brain8.md` item 1;
   - (b) a teacher-only prompt addendum for the permission family. Re-run with
     `teachers.py --only-ids <permission ids>` into a new out dir, then run `keep.py` and `export.py`, then `upload.py`.
2. Optional follow-up PR (`evals/` edit, needs lead OK): fix 8 v2 gold/accept rules that "append" with
   `type #ref "\n…"`, which replaces the field. Ids: v2-pages-no-target, v2-notes-into-search, v2-notes-text-missing,
   v2-note-delete-others, v2-doc-sysprompt, v2-pages-append, v2-note-checklist-item, v2-pages-type-save.
   Edit `evals/planner_v2_cat_*.py`, then run `planner_v2_build.py` and `planner_v2_validate.py`.
3. No Tinker run: the lead decides on a planner LoRA after the router it3 run.

**Reproduce / resume (about 10 minutes):**
```
python3 -m venv ~/venvs/demos && ~/venvs/demos/bin/pip install openai==1.109.1 anthropic==0.69.0 huggingface_hub==0.35.3 tokenizers==0.22.1
python3 training/planner_demos/build_states.py --out ~/data/planner_demos      # deterministic (seed 7) -> states.jsonl, states_report.json
# Optionally restore the paid replies instead of re-calling the APIs: download replies.jsonl.gz from HF and gunzip it to ~/data/planner_demos/replies.jsonl
~/venvs/demos/bin/python training/planner_demos/teachers.py --states ~/data/planner_demos/states.jsonl --out ~/data/planner_demos --openai-effort medium --conc 10 --budget-stop 85   # resumes, skipping (id, teacher) pairs already answered
~/venvs/demos/bin/python training/planner_demos/keep.py --dir ~/data/planner_demos      # -> built/demos.jsonl.gz, bank.jsonl.gz, keep_stats.json
~/venvs/demos/bin/python training/planner_demos/export.py --dir ~/data/planner_demos    # -> hf/ (reads git HEAD for meta)
~/venvs/demos/bin/python training/planner_demos/upload.py --dir ~/data/planner_demos/hf --repo jonsnov/muselet-planner-demos-v1
```

**Artifacts:**
- Code: branch `cloud/planner-demos` @ 9008990 (the data was built from code @ 99df4b6). PR https://github.com/ardahk/muselet/pull/33.
- HF dataset (private): `jonsnov/muselet-planner-demos-v1` @ 9453ff6. Files: `demos.jsonl.gz`, `bank.jsonl.gz`, `states.jsonl.gz`,
  `replies.jsonl.gz`, `meta.json`, `README.md`.
- Local run dir (the VM only, may be gone): `~/data/planner_demos/` (`pilot/` holds the 60-state pilot).
- Tinker: none.

**Spend so far:** $12.71 for the pilot plus the full run, and $0.06 for a smoke test, so **$12.77 of the $90 budget**.
Prices are $4 in / $20 out per 1M tokens for both teachers. OpenAI cached input is counted at 25%; Anthropic cache reads
at 10% and cache writes at 125%. `teachers.spend(dir)` recomputes the figure from `replies.jsonl`.

**Open questions for the lead:**
- Which fix for the permission-prompt demos, (a) or (b) above?
- Should I open the v2 append-rule fix PR?

**Gotchas:**
- `render.py` imports `brain.planner` with every missing third-party module stubbed (mlx, torch, tinker, ...). Run it with any
  Python ≥ 3.12; no MLX is needed. The system prompt deliberately has NO few-shot block (`prompts/planner_fewshot.md`).
- `type #ref "<text>"` replaces the whole field (AXValue in `Act.swift`). To append, type the existing text plus the new
  text. `keep.py` rejects replies that clobber non-empty fields; search, address and header fields and placeholders are exempt.
- The gate (`gate.py`) is a copy of `muselet_train.evalcheck`, which lives on `origin/cloud/data-pipeline` and is not on main.
  Short goals (≤ 5 tokens) are often dropped by the edit ≤ 1 rule, so the generators use longer goals.
- `build_states.py` must keep the same rng draws, or state ids and prompts change and the paid replies no longer match. Adding
  accept/reject patterns is safe; adding rng calls is not. Check with a before/after diff of goal, observation,
  last_batch and script_output.
- `teachers.py` counts the budget from its own `replies.jsonl`. The other lanes' spend (data-route ledger) is not included.
- `pkill -f upload.py` from a shell whose own command line contains "upload.py" kills that shell. Kill by pid instead.
- `upload.py` can hang after the commit has already landed. Check `HfApi().dataset_info(repo).sha`.
