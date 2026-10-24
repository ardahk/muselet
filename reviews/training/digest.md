# training review digest — pass 3
_2026-10-24T05:39:00Z_ · heads: main 10793e0, wip/local 1d7cc07, cloud/data-pipeline 4cbb74a, cloud/fixtures-docs 4bf2291, cloud/finance f098120 (no training-lane files)

## Open P0/P1 (ranked)
- **training-5** [P0] Chunked teacher doubles requests; 397B default can pass $150 — `training/src/muselet_train/teacher.py`
- **training-3** [P1] G3 context pairs mostly mislabeled: 21/37 sampled items wrong — `training/src/muselet_train/prompts.py`
- **training-9** [P1] ARGS datums not split with route twins; val labels leak — `training/src/muselet_train/dedup.py`
- **training-10** [P1] Eval filter silently runs without HobbyLM frozen tests — `training/src/muselet_train/dedup.py`
- **training-11** [P1] New ctx contract makes Finder selection=yes unreachable; training uses it — `AGENTS.md`
- **training-6** [P1] Contexts sampled independently of label contradict context-dependent supervision — `training/src/muselet_train/contexts.py`
- **training-7** [P1] ARGS targets fabricate unspoken values, incl. destructive move_to_trash paths — `training/src/muselet_train/prompts.py`
- **training-8** [P1] Adjudication verdicts never applied; 15% per-label STOP not computed — `training/src/muselet_train/adjudicate.py`

Resolved: training-1 (decontam filter on route+args), training-2, training-4. Open P2: training-12.

## Highest-leverage next moves
1. Before any teacher run: default 35B, pre-run $ estimate + abort, verify chunk-2 cached billing on a 500-item pilot (training-5).
2. Fix G3 pairing and wire adjudication verdicts + 15% STOP + asr.noise before full generation (training-3, -8).
3. Give args rows their route twin's split (training-9) and assert HobbyLM frozen tests loaded (training-10).
4. Constrain contexts per skill and reject unspoken ARGS values (training-6, -7).
5. Decide Finder selection semantics vs training contexts (training-11).
