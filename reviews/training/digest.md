# training review digest — pass 1
_2026-10-24T05:17:57Z_ · heads: main 7aacf99, wip/local b438799, cloud/data-pipeline 746450c, cloud/fixtures-docs 4bf2291

## Open P0/P1 (ranked)
- **training-1** [P0] 41/128 route_v1 eval utterances are verbatim generation-prompt examples — `training/src/muselet_train/prompts.py`
- **training-2** [P0] Spec 8-gram eval filter cannot match short items; no dedup/split code — `training/SPEC.md`
- **training-3** [P1] G3 context pairs mostly mislabeled: 21/37 sampled items wrong — `training/src/muselet_train/prompts.py`
- **training-4** [P1] Runtime special-option descriptions differ from training: 0/50 token parity — `ml/src/brain/decision.py`
- **training-5** [P1] Teacher defaults to 397B on full set with no cost guard — `training/src/muselet_train/teacher.py`
- **training-6** [P1] Contexts sampled independently of label contradict context-dependent supervision — `training/src/muselet_train/contexts.py`
- **training-7** [P1] ARGS targets fabricate unspoken values, incl. destructive move_to_trash paths — `training/src/muselet_train/prompts.py`
- **training-8** [P1] Adjudication verdicts never applied; 15% per-label STOP not computed — `training/src/muselet_train/adjudicate.py`

## Highest-leverage next moves
1. Decide how to de-contaminate route_v1 (fresh held-out route_v2 vs new prompt examples) before any route metric is reported (training-1/2).
2. Replace the 8-gram eval filter with exact + short-n-gram matching and group splits by source id (training-2).
3. Fix G3 (allow single-context items, adjudicate 100%) and regenerate the 2% sample before full gen (training-3, -8).
4. Runtime must read special-option descriptions from catalog.json; one shared parity artifact (training-4).
5. Default teacher to 35B + hard cost guard; re-budget Phase 1 at ~800 tok/route datum (training-5).
