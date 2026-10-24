# Cloud builder: benchmark harness (Muselet)

Repo `ardahk/muselet`. Read `AGENTS.md` first. Muselet is a fully on-device macOS computer-use agent (MLX on an
M5 Pro). Our claim must be "faster and more accurate than HobbyLM-1B Computer Use and DeskMind on their own
benchmarks, run on the same Mac". You build the harness and adapters here (Linux); the lead runs them on the Mac.
Fair comparison is non-negotiable: same machine, same task list, strict final-state grading, never trust a model's
"done", report p50/p95 latency and pass^k, and run the competitors with their own published commands.

Work on branch `cloud/bench` (from `main`), commit often, push, open one PR to `main` when done. Do not modify
`ml/src/brain/{decision,orchestrator,server,cli,catalog}.py`, `app/`, `evals/route_v1.jsonl` or `skills/` (other
agents own them); add new files. You have no API keys; everything you need is public.

## 1. `/v1/systemone` shim (serves DeskMind Bench, JevBench `typesafe`, LocalLLaMA/typed-decisions)
- Research the exact wire format from the sources, not from memory: github.com/deskmind-ai/brain (server code and
  `examples/request.json`), github.com/deskmind-ai/bench, github.com/fstandhartinger/jevbench (`typesafe` adapter),
  and the HF dataset `LocalLLaMA/typed-decisions` (`bench/score_with_jobs.sh`). Question kinds include `noul`
  (yes/no), `choice` and `score`. Save the request/response JSON Schemas and 3 real example payloads per benchmark
  under `bench/systemone/examples/`.
- Implement `bench/systemone/schema.py` (validation) and `bench/systemone/server.py` (stdlib `ThreadingHTTPServer`,
  `POST /v1/systemone`, `--port`, `--backend`), with a backend protocol
  `class Decider: def decide(self, state: str, question: dict) -> dict[str, float]` (option -> probability, sums to 1).
- Backends: `fake` (deterministic heuristic, for tests) and `mlx`: a new module `ml/src/brain/generic_decide.py`
  that renders any choice question with the vendored tinker-cookbook decision renderer
  (`ml/src/brain/vendor/tinker_decisions.py`) and the `AlphaChoiceRenderer` + `split_model` helpers from
  `brain.decision` (import only those names), and reads the answer distribution from one forward pass, exactly like
  `DecisionEngine.route`. Map `noul` to a 2-option choice and `score` to the benchmark's scale. Keep a cached
  static prefix where the payload allows. If mlx cannot install on Linux, test the `mlx` backend's rendering with
  only the tokenizer and leave the forward pass to the Mac.
- Tests: schema round-trips on the saved examples; the server answers every saved example with the fake backend.

## 2. Runners (commands the lead will run on the Mac)
- `bench/run_jevbench.sh` (public set, `--adapter typesafe` against our shim), `bench/run_typed_decisions.sh`
  (400-case test split), each writing results under `runs/bench/<name>/<timestamp>/` and printing accuracy,
  calibration (ECE/Brier/KL as each benchmark defines) and latency p50/p95.
- `bench/deskmind/README.md` + scripts: exact steps to (a) run DeskMind's own brain-0.8b/brain-4b on the Mac with
  their published commands, (b) run DeskMind Bench against our shim through their hands, and (c) run the 13 tasks
  with Muselet's own loop and grade with `deskmind-bench score`. List all 13 tasks with their graders in
  `bench/deskmind/tasks.md`.

## 3. HobbyLM replay
- Find HobbyLM's test requests (125-task live set and the frozen sets) and its graders/harness via the HF API
  (`huggingface.co/api/models/Hobbylm/hobbylm-1B-computer-use`, its files, and any linked GitHub repo; Apache-2.0).
  Vendor the request lists and grader definitions under `bench/hobbylm/` with a provenance note.
- `bench/hobbylm/replay.py`: for each task run setup, send the request through Muselet (the `hands serve --url
  ws://127.0.0.1:<port> --utterance "<text>"` CLI is a client that executes on the Mac), then grade by final Mac
  state (`defaults read`, AppleScript/JXA, file system, AX), recording pass/fail, false-done, time from utterance to
  first action and to verified completion. `--dry-run` prints the plan. Also a mode that runs HobbyLM itself with
  its published harness for the same tasks.
- `bench/hobbylm/coverage.md`: map each HobbyLM task to the Muselet skill or flow that should handle it (see
  `skills/catalog.json`), and list the gaps, ranked by how many tasks each gap blocks. This list is high priority.

## 4. Eval hygiene export
Write every external eval utterance you vendor (HobbyLM tests, DeskMind task prompts) to
`evals/external/utterances.jsonl` (`{"source", "id", "text"}`) so the router-training dedup filter can exclude them.

When done, reply with: the PR link, the exact commands for the Mac runs, the coverage gap list (top 10), and
anything you could not verify.
