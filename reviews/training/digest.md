# training review digest — pass 6
_heads: main c2d2988, cloud/data-pipeline 153a01c, cloud/bench 911a384, cloud/grounding 42310cd, cloud/brain-2 9f41c11 (self-poll, lead offline)_

## Open P0/P1 (ranked)
- **training-10** [P0] HobbyLM sealed-test items in training data; decontam can't read evals/external — `training/src/muselet_train/dedup.py`
- **training-3** [P1] G3 context pairs mostly mislabeled: 21/37 sampled items wrong — `training/src/muselet_train/prompts.py`
- **training-8** [P1] Adjudication narrowed below SPEC; verdicts, STOP gate, ASR unwired — `training/src/muselet_train/adjudicate.py`
- **training-5** [P1] Teacher guard assumes unverified 20% cached chunks; reserve short — `training/src/muselet_train/teacher.py`
- **training-13** [P1] v2 relabel regex misses catalog's own lock/trash phrasings — `training/src/muselet_train/relabel_v2.py`
- **training-14** [P1] main has catalog v2 but v1 parity samples; parity gate off — `training/artifacts/route_render_samples.jsonl`
- **training-15** [P1] Stratified teacher subset skews label prior and mixes hard/soft targets — `training/src/muselet_train/teacher.py`
- **training-9** [P1] ARGS datums not split with route twins; val labels leak — `training/src/muselet_train/dedup.py`
- **training-6** [P1] Contexts sampled independently of label contradict context-dependent supervision — `training/src/muselet_train/contexts.py`
- **training-7** [P1] ARGS targets fabricate unspoken values, incl. destructive move_to_trash paths — `training/src/muselet_train/prompts.py`
- **training-11** [P1] New ctx contract makes Finder selection=yes unreachable; training uses it — `AGENTS.md`

Resolved: training-1, training-2, training-4. Open P2: training-12.

## Highest-leverage next moves
1. Decontam against evals/external (read `text`), assert HobbyLM counts > 0, replace the 3 catalog examples that are HobbyLM sealed items (training-10).
2. Fix G3 pairing; apply A1 verdicts, adjudicate every flagged item, add the 15% STOP, wire asr.noise (training-3, -8).
3. Calibrate the teacher guard on a 200-item billed pilot (cached factor, reserve >= $38) (training-5); uniform-per-label teacher subset (training-15).
4. Land the 41-option render artifact on main and remove the parity xfails (training-14); v2 relabel by teacher score (training-13).
5. Split args rows with their route twins (training-9).
