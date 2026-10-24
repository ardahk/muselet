# training review digest — pass 4
_2026-10-24T05:55:04Z_ · heads: main dec310b, wip/local cbc4879, cloud/data-pipeline 8c7c023 (cloud/finance, advisor, bench, fixtures-docs: no training-lane files)

## Open P0/P1 (ranked)
- **training-5** [P0] 3-chunk teacher on 41 options: Phase 1 > $60 even on 35B — `training/src/muselet_train/teacher.py`
- **training-3** [P1] G3 context pairs mostly mislabeled: 21/37 sampled items wrong — `training/src/muselet_train/prompts.py`
- **training-8** [P1] Adjudication narrowed below SPEC; verdicts, STOP gate, ASR unwired — `training/src/muselet_train/adjudicate.py`
- **training-13** [P1] v2 relabel regex misses catalog's own lock/trash phrasings — `training/src/muselet_train/relabel_v2.py`
- **training-14** [P1] main has catalog v2 but v1 parity samples; parity gate off — `training/artifacts/route_render_samples.jsonl`
- **training-9** [P1] ARGS datums not split with route twins; val labels leak — `training/src/muselet_train/dedup.py`
- **training-10** [P1] Eval filter silently runs without HobbyLM frozen tests — `training/src/muselet_train/dedup.py`
- **training-6** [P1] Contexts sampled independently of label contradict context-dependent supervision — `training/src/muselet_train/contexts.py`
- **training-7** [P1] ARGS targets fabricate unspoken values, incl. destructive move_to_trash paths — `training/src/muselet_train/prompts.py`
- **training-11** [P1] New ctx contract makes Finder selection=yes unreachable; training uses it — `AGENTS.md`

Resolved: training-1, -2, -4. Open P2: training-12.

## Highest-leverage next moves
1. Teacher: 35B, one request per item, capped subset, pre-run $ abort — Phase 1 is >$60 as written (training-5).
2. Apply A1 verdicts, adjudicate every flagged item, add the 15% STOP, wire asr.noise (training-8); fix G3 pairing (training-3).
3. Pick v2 relabel candidates by v2 teacher score, not regex (training-13).
4. Land the 41-option render artifact on main and re-harden the parity test (training-14).
5. Split args rows with their route twins; assert HobbyLM frozen tests loaded (training-9, -10).
