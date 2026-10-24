# M5 Pro benchmark runbook (run in this order, from the muselet repo root)

## Document-app safety

The shared live harness, HobbyLM worker, and DeskMind runner inventory the
document apps a case may touch before setup or staging. A case is skipped as
`user_documents_open` if that inventory finds an existing window or document;
an inventory that cannot be trusted is skipped as
`user_documents_unverifiable`. Skipped cases do not receive setup or an
utterance. Teardown closes only case-created windows/documents identified by
captured window IDs or document name/path; broad close commands are forbidden.
The case's own close steps are never sent; only tracked created items are closed.
Re-run skipped cases before claiming a complete benchmark score. Terminal apps
are deliberately excluded from the document-app registry, so terminal-driven
changes remain a residual risk and must be reviewed separately.
Rows marked `harness_timeout` must be rerun before claiming a score.

Pins: DeskMind Bench `888035da50299f5523a5b55844a2114c4b8c6c3d` (suite diag-v27, hash 5eec62a0c662),
DeskMind Hands `89be730acdbdd50a77bb6ac44583e190c719a14a`, DeskMind Brain `dadf97d01512f6384ca8bfd90a77cc88ae1a2f43`,
HobbyLM `4ea1389b68f5a6f7ec72200543fd8374c14d4526`. JevBench and Typed Decisions are pinned inside their scripts.
Close Mail, Messages and any app holding user documents before starting.

Before any case-specific precondition, document guard, setup, or utterance,
the live suite, HobbyLM replay modes, and DeskMind runner invoke the selected
HandsKit binary's `probe session` command with a five-second timeout. Locked
or asleep sessions are skipped as `screen_locked`; failed or invalid probes
are `session_unverifiable`. These cases get no setup, utterance, teardown, or
restore, and DeskMind records them in `skipped.jsonl`. Dry runs only display
the planned probe. As required by `AGENTS.md`, results gathered while the
screen is locked are invalid.

## 0. One-time setup
```sh
git fetch origin && git checkout cloud/bench && git pull
uv sync --project ml
(cd app && swift build -c release)
export HANDS_BIN="$PWD/app/.build/release/hands"
uv run --project ml python -m pytest bench/tests -q

mkdir -p ../bench-ext && cd ../bench-ext
git clone https://github.com/deskmind-ai/bench && git -C bench checkout 888035da50299f5523a5b55844a2114c4b8c6c3d
git clone https://github.com/deskmind-ai/hands && git -C hands checkout 89be730acdbdd50a77bb6ac44583e190c719a14a
git clone https://github.com/deskmind-ai/brain && git -C brain checkout dadf97d01512f6384ca8bfd90a77cc88ae1a2f43
python3 -m venv dm-venv && dm-venv/bin/pip install -e ./hands -e "./bench[run]"
(cd brain && uv sync --extra mlx \
  && uv run hf download deskmind/brain-0.8b --revision g18b-q8 --local-dir models/brain-0.8b \
  && uv run hf download deskmind/brain-4b --revision g18b-q8 --local-dir models/brain-4b)
pip3 install -U huggingface_hub
hf download Hobbylm/hobbylm-1B-computer-use --revision 4ea1389b68f5a6f7ec72200543fd8374c14d4526 --local-dir hobby-mac
(cd hobby-mac && chmod +x scripts/setup.sh && ./scripts/setup.sh)
cd ../muselet
export DM="$PWD/../bench-ext" HOBBY_HOME="$PWD/../bench-ext/hobby-mac"
```

## 1. Benchmark calendar (local, no attendees)
```sh
uv run --project ml python -m bench.hobbylm.calendar_safety setup   # creates "Muselet Bench" in On My Mac only
# Calendar > Settings > General > Default calendar: Muselet Bench
uv run --project ml python -m bench.hobbylm.calendar_safety probe   # must print source_type "local", is_default_for_new_events true
```
If probe is not local+default, event tasks are skipped, never run.

## 2. Dry runs (no OS actions)
```sh
uv run --project ml python bench/hobbylm/replay.py --system muselet --round r4 --dry-run
uv run --project ml python bench/hobbylm/replay.py --system hobbylm --round r4 --dry-run
uv run --project ml python bench/live/run_live.py --dry-run --tier T1 --tier T2
uv run --project ml python bench/deskmind/run_muselet.py --dry-run
```

## 3. System One decision benchmarks (locale-independent; one server at a time)
```sh
# 3a Muselet shim (terminal A), then runners (terminal B), then stop the shim
PYTHONPATH=ml/src uv run --project ml python -m bench.systemone.cli --host 127.0.0.1 --port 8793 \
  --backend mlx --model-path mlx-community/Qwen3.5-4B-4bit --model-name muselet
# For a calibrated export, add --calibration runs/decisions/export/<name>/mlx4/calibration.json.
# The same option works with --backend tinker; do not combine it with non-default temperature flags.
bash bench/run_jevbench.sh --url http://127.0.0.1:8793 --model muselet
bash bench/run_typed_decisions.sh --url http://127.0.0.1:8793 --model muselet
# 3b DeskMind brain-0.8b (terminal A: (cd $DM/brain && uv run deskmind-brain-serve --predictor mlx:models/brain-0.8b --port 8794))
bash bench/run_jevbench.sh --url http://127.0.0.1:8794 --model brain-0.8b
bash bench/run_typed_decisions.sh --url http://127.0.0.1:8794 --model brain-0.8b
# 3c DeskMind brain-4b (terminal A: (cd $DM/brain && uv run deskmind-brain-serve --predictor mlx:models/brain-4b --port 8795))
bash bench/run_jevbench.sh --url http://127.0.0.1:8795 --model brain-4b
bash bench/run_typed_decisions.sh --url http://127.0.0.1:8795 --model brain-4b
```

## 4. HobbyLM r4, both systems, same harness clock and grader (English locale)
```sh
# 4a HobbyLM through its own trial() in the parent-clocked worker (no Muselet brain running)
uv run --project ml python bench/hobbylm/replay.py --system hobbylm --round r4 --repeats 3 --hobby-home "$HOBBY_HOME"
# 4b Muselet: brain in terminal A, replay in terminal B
uv run --project ml python -m brain.cli serve --port 8765 \
  --model mlx-community/Qwen3.5-4B-4bit --planner-model mlx-community/Qwen3.5-4B-4bit
uv run --project ml python bench/hobbylm/replay.py --system muselet --round r4 --repeats 3 \
  --external-brain --port 8765 --hands-bin "$HANDS_BIN"
```

## 5. Muselet live suite (brain from 4b still running)
```sh
uv run --project ml python bench/live/run_live.py --suite evals/live_t1.jsonl --brain-url ws://127.0.0.1:8765 \
  --proxy-port 8790 --hands-bin "$HANDS_BIN" --tier T1 --tier T2 --repeat 3
```
`--include-pending` reports pending cases as skipped without a session probe or
any setup or utterance. Use `--run-pending` to execute them through the full
guarded path; cases marked `requires_user_ok` also require `--allow-user-ok`.
For example, inspect the pending T2 cases with
`uv run --project ml python bench/live/run_live.py --dry-run --tier T2 --include-pending`,
or preview execution with
`uv run --project ml python bench/live/run_live.py --dry-run --tier T2 --run-pending --allow-user-ok`.

### 5b. New-capability multi-turn cases (`evals/live_t2_new.jsonl`: memory, Clock, again/undo, Notes)
Six T2 cases; four use `turns` (sent in order by one `hands serve` client on one brain WebSocket, so
working memory carries over; the proxy holds each next utterance until the previous turn's outcome,
`wait_s` and per-turn checks are done). Before running: quit Safari and Chrome (`mem-wiki-search`
needs neither running, and is skipped by `--offline`), quit Notes and Clock, close every Finder
window, no Clock timer running, and no document-app windows open (`notes-template` inventories every
document app). A failed precondition is a SKIP, never a manual workaround.
```sh
# plan only (no OS actions): lists every turn per case
uv run --project ml python bench/live/run_live.py --suite evals/live_t2_new.jsonl --dry-run
# only the new cases
uv run --project ml python bench/live/run_live.py --suite evals/live_t2_new.jsonl --brain-url ws://127.0.0.1:8765 \
  --proxy-port 8790 --hands-bin "$HANDS_BIN" --repeat 3 --out runs/bench/live/t2new-$(date -u +%Y%m%dT%H%M%SZ)
# one case, or one category (memory | timers | notes)
uv run --project ml python bench/live/run_live.py --suite evals/live_t2_new.jsonl --brain-url ws://127.0.0.1:8765 \
  --proxy-port 8790 --hands-bin "$HANDS_BIN" --id mem-again-volume
uv run --project ml python bench/live/run_live.py --suite evals/live_t2_new.jsonl --brain-url ws://127.0.0.1:8765 \
  --proxy-port 8790 --hands-bin "$HANDS_BIN" --category memory
# whole suite: live_t1 then live_t2_new, same brain, separate result dirs
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
uv run --project ml python bench/live/run_live.py --suite evals/live_t1.jsonl --brain-url ws://127.0.0.1:8765 \
  --proxy-port 8790 --hands-bin "$HANDS_BIN" --tier T1 --tier T2 --repeat 3 --out runs/bench/live/t1-$STAMP
uv run --project ml python bench/live/run_live.py --suite evals/live_t2_new.jsonl --brain-url ws://127.0.0.1:8765 \
  --proxy-port 8790 --hands-bin "$HANDS_BIN" --repeat 3 --out runs/bench/live/t2new-$STAMP
```
Each multi-turn result row has `turns` (per turn: `utterance`, `status`, `observed_outcome`, `mood`,
`reply`, `latency_s`, `first_action_latency_s`, `check_observations`, `passed`), `turns_ok` and
`saved_values`; `strict_pass` also requires `turns_ok`. Stop the brain afterwards.

## 6. DeskMind diag-v27 (zh-Hans for every system)
Put Simplified Chinese first in System Settings > General > Language & Region, log out and in, then
`defaults read -g AppleLanguages` must list zh-Hans first.
```sh
mkdir -p runs/deskmind/brain-0.8b-runs runs/deskmind/brain-4b-runs runs/deskmind/muselet-shim-runs
# 6a DeskMind brain-0.8b (terminal A as in 3b, port 8794)
(cd runs/deskmind/brain-0.8b-runs && \
  DESKMIND_RUNS_DIR=. $DM/dm-venv/bin/deskmind-bench run --set diag --repeats 3 --url http://127.0.0.1:8794 --label brain-0.8b --out ../brain-0.8b.json)
# 6b DeskMind brain-4b (terminal A as in 3c, port 8795)
(cd runs/deskmind/brain-4b-runs && \
  DESKMIND_RUNS_DIR=. $DM/dm-venv/bin/deskmind-bench run --set diag --repeats 3 --url http://127.0.0.1:8795 --label brain-4b --out ../brain-4b.json)
# 6c Muselet shim through DeskMind Hands (terminal A as in 3a, port 8793)
(cd runs/deskmind/muselet-shim-runs && \
  DESKMIND_RUNS_DIR=. $DM/dm-venv/bin/deskmind-bench run --set diag --repeats 3 --url http://127.0.0.1:8793 --label muselet-shim --out ../muselet-shim.json)
# 6d Muselet's own loop (terminal A: brain as in 4b)
uv run --project ml python bench/deskmind/run_muselet.py --repeats 3 --port 8765 --hands-command "$HANDS_BIN" --deskmind-python "$DM/dm-venv/bin/python" --bench-dir "$DM/bench"
# 6e Regrade everything with the same scorer and suite version
for r in brain-0.8b brain-4b muselet-shim; do
  (cd runs/deskmind/$r-runs && \
    $DM/dm-venv/bin/deskmind-bench score ../$r.json --suite-version diag-v27 --out ../$r.score.json && \
    $DM/dm-venv/bin/deskmind-bench table ../$r.score.json)
done
$DM/dm-venv/bin/deskmind-bench score runs/bench/deskmind/muselet --suite-version diag-v27 --out runs/bench/deskmind/muselet/score.json
$DM/dm-venv/bin/deskmind-bench table runs/bench/deskmind/muselet/score.json
```
Restore your language order afterwards.

## 7. Cleanup
Stop every server. Delete the `Muselet Bench` calendar if you no longer need it.

## Mac results (2026-10-24, lead's run)

| System | JevBench (public) | JevBench hard | Typed Decisions (400 test) |
|---|---:|---:|---:|
| Muselet System One shim, base Qwen3.5-4B (no LoRA) | 0.719 | 0.523 | 0.569 |
| DeskMind brain-4b (`deskmind-brain-serve`) | 0.831 | not reported | 0.658 |

brain-serve returns noul and score answers without probabilities. From this commit on,
`typed_decisions.py` converts them, noul to `{false: 1-p, true: p}` and score to one-hot at the
half-up rounded value, and records the counts in `summary.json` `normalized_answers`. The 0.658
above predates that counter, so rerun brain-4b to get the disclosed counts. One-hot scores also
inflate KL and Brier for score questions.
