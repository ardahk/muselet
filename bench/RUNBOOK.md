# M5 Pro benchmark runbook

Run every command from the repository root. The commands below use only the
shipped benchmark CLIs and keep all inference local.

## Preflight

```sh
uv sync --project ml
uv run --project ml python -m pytest bench/tests -q
uv run --project ml python -m compileall -q bench ml/src/brain/generic_decide.py ml/src/brain/decision_chunking.py
```

For DeskMind comparisons, install the public Hands checkout at commit
`89be730acdbdd50a77bb6ac44583e190c719a14a`, and put `zh-Hans` first in
**System Settings > General > Language & Region > Preferred Languages**.
The DeskMind runner refuses another installed Hands commit or locale.

## Dry runs

```sh
python3 bench/hobbylm/replay.py --system muselet --round r4 --dry-run
python3 bench/hobbylm/replay.py --system hobbylm --round r4 --dry-run
python3 bench/live/run_live.py --dry-run --tier T1
python3 bench/deskmind/run_muselet.py --dry-run
```

## Muselet live suite

Start Brain with System 1 and the planner model on separate local model
snapshots. The shipped Brain CLI flags are:

```sh
uv run --project ml python -m brain.cli serve \
  --port 8765 \
  --model mlx-community/Qwen3.5-0.8B-4bit \
  --planner-model mlx-community/Qwen3.5-4B-4bit
```

In a second terminal, run the selected live tiers:

```sh
python3 bench/live/run_live.py --tier T1 --out runs/bench/live/t1
```

Use `--include-pending` and `--include-manual` only when the Mac is prepared
for those cases. The safety guard is on by default; `--no-safety-guard` is
unsafe and must be labelled as such in the resulting report.

## DeskMind diag-v27

```sh
python3 bench/deskmind/run_muselet.py --repeats 3 --port 8765
deskmind-bench score runs/bench/deskmind/muselet \
  --suite-version diag-v27 \
  --out runs/bench/deskmind/muselet/score.json
deskmind-bench table runs/bench/deskmind/muselet/score.json
```

Compare only with DeskMind Brain 0.8b/4b runs made on the same Mac, locale,
suite hash `5eec62a0c662`, and Hands pin.

## HobbyLM

Set `HOBBY_HOME` to the pinned external HobbyLM checkout and use its `.venv`
for the worker:

```sh
python3 bench/hobbylm/replay.py --system hobbylm --round r4 --repeats 1
python3 bench/hobbylm/replay.py --system muselet --round r4 --repeats 1
```

Event cases run only after the EventKit probe proves `Muselet Bench` exists in
a local source and is the default calendar. Set that in **Calendar >
Settings > General > Default calendar**. Stop Brain and Hands when the run is
complete; never leave a benchmark server running.
