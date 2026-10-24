# System One shim

Run the deterministic local backend from the repository root:

```sh
python3 -m bench.systemone.cli --host 127.0.0.1 --port 8793 --backend fake --model-name muselet
```

The server implements `POST /v1/systemone` and `GET /v1/models`. The optional MLX backend is selected with
`--backend mlx --model-path <local-model-directory>` on a Mac with the matching `brain.decision` and
`brain.vendor.tinker_decisions` files available. Backend inference is serialized across HTTP worker threads.

The schemas in `examples/` and the stdlib parser in `schema.py` mirror DeskMind Brain's ordered choice criteria,
ordinal score levels, request identity, normalization and confidence formulas. The additional `probabilities` member
on `noul` answers is intentional: JevBench consumes `noul`, while Typed Decisions consumes that distribution.
Examples are generated with `python3 -m bench.systemone.examples.build_examples`; the README in that directory
records their exact source revisions and row identifiers.

The saved DeskMind fixtures include requests above the local renderer's 58-choice alphabet. The schema and fake
backend accept them; the MLX backend returns `invalid_request` with `too_many_options` rather than silently dropping
options.
