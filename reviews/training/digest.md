# training review digest: pass 7
_heads: main c2d2988, cloud/data-pipeline 8f0b9bc (Phase 1 trainer, pilot LR sweep, export/MLX parity), others unchanged. Self-poll; the lead is offline._

## Open P0/P1 (ranked)
- **training-10** [P0] HobbyLM sealed-test items are in the training data, and decontam can't read evals/external (`training/src/muselet_train/dedup.py`). The trainer is now ready, so the main run could launch on contaminated data.
- **training-16** [P1] ASR noise rewrites the ARGS inputs but keeps the clean copy-exact targets; 34 of 214 noised items are affected (`training/src/muselet_train/datums.py`).
- **training-3** [P1] G3 context pairs are mostly mislabeled: 21 of 37 sampled items are wrong (`training/src/muselet_train/prompts.py`).
- **training-17** [P1] In the pilots, finance_review val accuracy is 0–25% (likely about 4 items), and it's a demo-critical skill (`training/reports/phase1_pilot-lr4e-4.md`).
- **training-5** [P1] Phase 1 spend is unverified (no billed figure for any run), and training alone (about $38.4) exceeds TRAIN_RESERVE $35 (`training/src/muselet_train/train.py`).
- **training-8** [P1] Adjudication is narrower than SPEC and has no 15% STOP gate. Verdicts and ASR noise are now wired (`training/src/muselet_train/adjudicate.py`).
- **training-13** [P1] The v2 relabel regex misses the catalog's own lock-screen and trash phrasings (`training/src/muselet_train/relabel_v2.py`).
- **training-14** [P1] main has catalog v2 but the v1 parity samples, so the parity gate is off (`training/artifacts/route_render_samples.jsonl`).
- **training-15** [P1] The stratified teacher subset skews the label prior and mixes hard and soft targets (`training/src/muselet_train/teacher.py`).
- **training-6** [P1] Contexts are sampled independently of the label, which contradicts context-dependent supervision (`training/src/muselet_train/contexts.py`).
- **training-7** [P1] ARGS targets invent values the user never said, including destructive move_to_trash paths (`training/src/muselet_train/prompts.py`).
- **training-11** [P1] The new context contract makes Finder selection=yes unreachable, but training uses it (`AGENTS.md`).

Resolved: training-1, training-2, training-4. Open P2: training-9 (residual: ARGS rows default to train), training-12, training-18 (only the final checkpoint is exported, no best-val pick), training-19 (mixed batches drop 16–21% of the data).

## Highest-leverage next moves
1. Gate the main run on decontam against evals/external (read `text`, assert HobbyLM count > 0) and replace the 3 catalog examples that are HobbyLM sealed items (training-10).
2. Apply noise to route datums only; ARGS gets fillers and false starts outside arg spans, or no noise (training-16). Fix G3 pairing and add the 15% STOP gate (training-3, training-8).
3. Record the `tinker billing` figure for the pilots and the teacher pilot. Set main-run --max-usd = 60 minus billed spend so far, and raise TRAIN_RESERVE to at least $40 (training-5).
4. Before the full run, inspect finance_review vs MULTI_STEP on v2all, and evaluate on the full val split (training-17, training-13).
5. Save sampler weights at each eval and export the best-val step. Cycle the shorter datum list in mixed batches (training-18, training-19).
