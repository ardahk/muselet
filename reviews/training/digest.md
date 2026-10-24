# training review digest — pass 2
_2026-10-24T05:24:27Z_ · heads: main a5e76fa, wip/local bcd3b75, cloud/data-pipeline 56ef91b, cloud/fixtures-docs 4bf2291

## Open P0/P1 (ranked)
- **training-1** [P0] 41/128 route_v1 eval utterances are verbatim generation-prompt examples — `training/src/muselet_train/prompts.py`
- **training-9** [P0] ARGS datums bypass dedup/eval filter/split, leaking route labels — `training/src/muselet_train/dedup.py`
- **training-3** [P1] G3 context pairs mostly mislabeled: 21/37 sampled items wrong — `training/src/muselet_train/prompts.py`
- **training-10** [P1] Eval filter silently runs without HobbyLM tests and on stale route_v1 — `training/src/muselet_train/dedup.py`
- **training-11** [P1] New ctx contract makes Finder selection=yes unreachable; training uses it — `AGENTS.md`
- **training-5** [P1] Teacher defaults to 397B on full set with no cost guard — `training/src/muselet_train/teacher.py`
- **training-6** [P1] Contexts sampled independently of label contradict context-dependent supervision — `training/src/muselet_train/contexts.py`
- **training-7** [P1] ARGS targets fabricate unspoken values, incl. destructive move_to_trash paths — `training/src/muselet_train/prompts.py`
- **training-8** [P1] Adjudication verdicts never applied; 15% per-label STOP not computed — `training/src/muselet_train/adjudicate.py`

Resolved this pass: training-2 (char 8-gram dedup/split landed), training-4 (runtime reads catalog special_options; artifacts identical).

## Highest-leverage next moves
1. Split/filter args.jsonl with its route twin (same src+utterance) before any pilot; otherwise val accuracy and checkpoint pick are inflated (training-9).
2. Merge main into cloud/data-pipeline, assert HobbyLM frozen tests are loaded, then rerun dedup (training-10); fix route_v1:89/114/116 (training-1).
3. Fix G3 (single-context allowed, 100% adjudication) and wire adjudication verdicts + 15% STOP + asr.noise before full gen (training-3, -8).
4. Default teacher to 35B with a hard pre-run $ estimate (training-5).
5. Decide Finder selection semantics in the ctx contract vs training contexts (training-11).
