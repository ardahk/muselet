
## Your lane: `bench` — benchmark harness and comparison fairness
Files: `bench/*` (incl. `bench/systemone/`, `bench/deskmind/`, `bench/hobbylm/`, runners, `speed_lab.py`),
`ml/src/brain/generic_decide.py`, `evals/external/*`. Work arrives on branch `cloud/bench` (a cloud builder) and
later on `main`/`wip/local`. Read `cloud/builder_bench.md`: it is the spec.
Look hardest at:
- Wire-format fidelity: verify against the upstream sources (deskmind-ai/brain + bench, jevbench `typesafe`,
  LocalLLaMA/typed-decisions) that the shim accepts their real payloads and returns what their scorers parse.
- Probability correctness: distributions sum to 1, option order/ids map back correctly, `noul`/`score` handled the
  way each scorer expects, and the rendered prompt for the MLX backend is token-correct.
- Fairness: competitors run with their own published commands and settings on the same Mac; same task lists;
  strict final-state grading; false-done counted; latency measured end to end the same way for everyone; no
  cherry-picking or retries hidden from the results.
- HobbyLM replay: graders really check final state; setup/teardown isolate tasks; the coverage map is accurate.
- Eval hygiene: external utterances exported for the training dedup filter.
