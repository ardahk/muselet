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

The protocol accepts up to 255 choice options. An MLX renderer pass supports up to 58 usable labels; requests with
more options use a two-stage approximation. The first stage scores contiguous, balanced chunks, then the second
stage chooses among each chunk's winner. The returned probability for an option is its within-chunk probability
multiplied by that chunk winner's second-stage probability. Requests with 58 or fewer options use the original
single-stage path. MLX reports rendered prompt tokens fed across the request in `usage.input_tokens`; cached static
prefix tokens are excluded. The fake backend reports `null` for that field.
