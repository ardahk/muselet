# System One shim

Run the deterministic local backend from the repository root:

```sh
python3 -m bench.systemone.cli --host 127.0.0.1 --port 8793 --backend fake --model-name muselet
```

The server implements `POST /v1/systemone` and `GET /v1/models`. The optional MLX backend is selected with
`--backend mlx --model-path <local-model-directory>` on a Mac with the matching `brain.decision` and
`brain.vendor.tinker_decisions` files available. Backend inference is serialized across HTTP worker threads.

The cloud sampler backend uses the shared Qwen renderer and is selected with
`--backend tinker --model-path <base-model-or-tinker-uri>`. Install its optional SDK with
`uv sync --project ml --extra tinker`; the project's existing `tinker-cookbook` pin is reused.

For either the `mlx` or `tinker` backend, pass `--calibration <path>` to load
`temperature_probs` and `temperature_conf` from a calibration JSON file. The file values
calibrate the answer probabilities and confidence distribution separately. Do not combine
`--calibration` with non-default `--temperature-probs` or `--temperature-conf` flags; without
a file, the temperature flags remain available directly.

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
