# decisions — digest (pass 1)

`cloud/decisions` does not exist yet; pass 1 reviews the brief (main 1ce501b) and the code it will reuse
(cloud/data-pipeline a6b229a, cloud/bench 2c57d7f). No P0: no decisions training data exists to leak.

## Open P0/P1
1. decisions-1 P1 Decontam index lacks JevBench/typed-decisions; no 13-gram or option-set test — training/src/muselet_train/decontam.py
2. decisions-3 P1 Route regression would be measured with the wrong renderer and n=140 — cloud/builder_decisions.md
3. decisions-5 P1 Before/after benchmark numbers would mix MLX-4bit and Tinker-bf16 — cloud/builder_decisions.md
4. decisions-4 P1 noul option order flips with criteria presence — ml/src/brain/generic_decide.py
5. decisions-2 P1 Identical-option-set rule is degenerate on benchmark option sets — cloud/builder_decisions.md

## Highest-leverage next moves
- Write the decisions decontam (JevBench@609a664 + td@80cb93a, 13-gram containment + defined option-set rule) before generating data.
- Commit a generic-path token parity artifact + test; Tinker Decider imports _decision/_choices.
- Route regression via eval_route.py on val + route_v1, paired, both checkpoints.
- Same-backend before/after; headline only from MLX with quantization stated.
- Post token/$ estimate (~$15/epoch for 20k + 30% replay) before launch.
