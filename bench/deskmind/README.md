# DeskMind Bench comparisons

Pinned comparison: DeskMind Bench `diag-v27`, suite hash `5eec62a0c662`,
public DeskMind Hands commit `89be730acdbdd50a77bb6ac44583e190c719a14a`,
locale `zh-Hans`. The Muselet runner refuses a different suite hash or installed
Hands commit. Compare Muselet only with DeskMind run on the same Mac at this
pin; published numbers made with another harness version are not comparable.
The reference run requires macOS and Peekaboo. Before all compared runs, use
System Settings > General > Language & Region > Preferred Languages to put
Simplified Chinese first, verify `defaults read -g AppleLanguages` includes
`zh-Hans`, then restore the previous order after benchmarking.

## Published Brain baselines

The complete M5 Pro sequence is in [`../RUNBOOK.md`](../RUNBOOK.md). Commands
below are from the pinned Brain README. Run both model sizes through the pinned
DeskMind Bench suite, then through the JevBench and Typed Decisions scripts in
this repository:

```sh
uv run hf download deskmind/brain-0.8b --revision g18b-q8 --local-dir models/brain-0.8b
uv run deskmind-brain-serve --predictor mlx:models/brain-0.8b --port 8794
mkdir -p runs/deskmind/brain-0.8b-runs
(cd runs/deskmind/brain-0.8b-runs && \
  DESKMIND_RUNS_DIR=. deskmind-bench run --set diag --repeats 3 --url http://127.0.0.1:8794 \
  --label brain-0.8b --out ../brain-0.8b.json)
uv run hf download deskmind/brain-4b --revision g18b-q8 --local-dir models/brain-4b
uv run deskmind-brain-serve --predictor mlx:models/brain-4b --port 8795
mkdir -p runs/deskmind/brain-4b-runs
(cd runs/deskmind/brain-4b-runs && \
  DESKMIND_RUNS_DIR=. deskmind-bench run --set diag --repeats 3 --url http://127.0.0.1:8795 \
  --label brain-4b --out ../brain-4b.json)
```

Regrade the report files and inspect per-task results with the same pinned
scorer:

```sh
for r in brain-0.8b brain-4b; do
  (cd runs/deskmind/$r-runs && \
    deskmind-bench score ../$r.json --suite-version diag-v27 --out ../$r.score.json && \
    deskmind-bench table ../$r.score.json)
done
```

Compare each baseline on public typed-decision suites as well:

```sh
bash bench/run_jevbench.sh --url http://127.0.0.1:8794 --model brain-0.8b
bash bench/run_typed_decisions.sh --url http://127.0.0.1:8794 --model brain-0.8b
bash bench/run_jevbench.sh --url http://127.0.0.1:8795 --model brain-4b
bash bench/run_typed_decisions.sh --url http://127.0.0.1:8795 --model brain-4b
```

## Muselet

Start the System One shim and use the pinned DeskMind Bench Hands adapter:

```sh
PYTHONPATH=ml/src uv run --project ml python -m bench.systemone.cli --host 127.0.0.1 --port 8793 \
  --backend mlx --model-path mlx-community/Qwen3.5-4B-4bit --model-name muselet
mkdir -p runs/deskmind/muselet-shim-runs
(cd runs/deskmind/muselet-shim-runs && \
  DESKMIND_RUNS_DIR=. deskmind-bench run --set diag --repeats 3 --url http://127.0.0.1:8793 \
  --label muselet-shim --out ../muselet-shim.json)
(cd runs/deskmind/muselet-shim-runs && \
  deskmind-bench score ../muselet-shim.json --suite-version diag-v27 --out ../muselet-shim.score.json && \
  deskmind-bench table ../muselet-shim.score.json)
```

The shim comparisons isolate protocol compatibility; they are not a claim about
Muselet's native desktop policy. Native loop replay is available on macOS with a
running local Muselet brain and Hands CLI:

```sh
uv run --project ml python bench/deskmind/run_muselet.py --repeats 3 --port 8765
deskmind-bench score runs/bench/deskmind/muselet --suite-version diag-v27 --out runs/bench/deskmind/muselet/score.json
deskmind-bench table runs/bench/deskmind/muselet/score.json
```

Each run folder contains `manifest.json`, `run.json`, `trace.jsonl`, and `ws/`;
grading is repeated from the final workspace by `deskmind-bench score`. The
runner unpacks the pinned fixture, applies each task's `reset_apps` and ordered
`stage` commands with `$WS` bound to that run's workspace, opens Finder on the
workspace when the task has no explicit stage, and passes `task.goal` exactly
as loaded by the pinned `load_task` (trimmed only as that loader trims it).
Local Safari fixture pages are served over loopback HTTP, matching the pinned
Hands staging behavior; those per-run servers are stopped after each trial.
Task wall-clock budgets begin after fixture staging and app setup, as they do
in the pinned runner. TextEdit reset closes only documents under this runner's
workspace, and reset-app checks do not launch apps that were not already open.
The pinned suite requires macOS `AppleLanguages` to include `zh-Hans`, which
the runner checks before replay. DeskMind Brain 0.8b/4b, the shim, and Muselet loop must all use `zh-Hans` and the exact public Hands pin above. Since Muselet receives the app context from
the live desktop rather than a task-app override, the primary staged app is
opened in the foreground; secondary staged apps use `open -g`. This differs
from Bench's pinned-window observation but ensures the Muselet utterance starts
with the task's declared app frontmost. The task definitions have no `vars`;
the pinned grader's `${NAME}` substitutions apply only to grader predicates,
not to the goal sent to the planner. This live workflow is not run on Linux.

## Task definitions

[`tasks.md`](tasks.md) is generated from all 13 pinned diagnostic YAML files
and includes the original goal, English gloss, fixture, checkpoints, guards,
forbids, and sentinels.
