# DeskMind Bench comparisons

Pinned reference revisions: Brain `dadf97d01512f6384ca8bfd90a77cc88ae1a2f43`,
Bench `888035da50299f5523a5b55844a2114c4b8c6c3d`, and Hands
`3c1ceac6e1918b656d56728c5fef1bc6726462f3`. The reference run requires a Mac,
Peekaboo, the published Bench environment and the `zh-Hans` locale.

## Published Brain baselines

Commands below are from the pinned Brain README. Run both model sizes through
the pinned DeskMind Bench suite, then through the JevBench and Typed Decisions
scripts in this repository:

```sh
uv run hf download deskmind/brain-0.8b --revision g18b-q8 --local-dir models/brain-0.8b
uv run deskmind-brain-serve --predictor mlx:models/brain-0.8b --port 8794
deskmind-bench run --set diag --repeats 3 --url http://127.0.0.1:8794 --label brain-0.8b --out runs/deskmind/brain-0.8b
uv run hf download deskmind/brain-4b --revision g18b-q8 --local-dir models/brain-4b
uv run deskmind-brain-serve --predictor mlx:models/brain-4b --port 8793
deskmind-bench run --set diag --repeats 3 --url http://127.0.0.1:8793 --label brain-4b --out runs/deskmind/brain-4b
```

Compare each baseline on public typed-decision suites as well:

```sh
bash bench/run_jevbench.sh --url http://127.0.0.1:8794 --model brain-0.8b
bash bench/run_typed_decisions.sh --url http://127.0.0.1:8794 --model brain-0.8b
bash bench/run_jevbench.sh --url http://127.0.0.1:8793 --model brain-4b
bash bench/run_typed_decisions.sh --url http://127.0.0.1:8793 --model brain-4b
```

## Muselet

Start the System One shim and use the pinned DeskMind Bench Hands adapter:

```sh
python3 -m bench.systemone.cli --host 127.0.0.1 --port 8793 --backend fake
deskmind-bench run --set diag --repeats 3 --url http://127.0.0.1:8793 --label muselet-shim --out runs/deskmind/muselet-shim
```

The shim comparisons isolate protocol compatibility; they are not a claim about
Muselet's native desktop policy. Native loop replay is available on macOS with a
running local Muselet brain and Hands CLI:

```sh
python3 bench/deskmind/run_muselet.py --repeats 3 --port 8765
deskmind-bench score runs/bench/deskmind/muselet --suite-version diag-v25 --out runs/bench/deskmind/muselet/score.json
deskmind-bench table runs/bench/deskmind/muselet/score.json
```

Each run folder contains `manifest.json`, `run.json`, `trace.jsonl`, and `ws/`;
grading is repeated from the final workspace by `deskmind-bench score`. Muselet
must be connected to a live brain server. This live workflow is not run on Linux.

## Task definitions

[`tasks.md`](tasks.md) is generated from all 13 pinned diagnostic YAML files
and includes the original goal, English gloss, fixture, checkpoints, guards,
forbids, and sentinels.
