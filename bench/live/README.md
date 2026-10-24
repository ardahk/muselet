# Live suite

The live runner executes `evals/live_t1.jsonl` against a macOS desktop. It
starts a local WebSocket proxy and launches `hands serve` clients as needed;
start the Brain server separately. Do not run the suite while another person
is using the desktop. Grant the app the required Accessibility, Automation,
and Screen Recording permissions before running it.

## Build and start

From the repository root on the Mac:

```sh
cd app
swift build -c release
cd ..
uv run --project ml python -m brain.cli serve --port 8765
```

Leave Brain running in that terminal. In a second terminal, run the suite with
the HandsKit binary built above; the runner starts its proxy on port 8790:

```sh
uv run --project ml python bench/live/run_live.py \
  --suite evals/live_t1.jsonl \
  --brain-url ws://127.0.0.1:8765 \
  --proxy-port 8790 \
  --hands-bin "$PWD/app/.build/release/hands" \
  --tier T1
```

T2 uses the same runner and keeps manual, pending, online, and consent-gated
cases skipped unless explicitly opted in:

```sh
uv run --project ml python bench/live/run_live.py \
  --suite evals/live_t1.jsonl \
  --brain-url ws://127.0.0.1:8765 \
  --proxy-port 8790 \
  --hands-bin "$PWD/app/.build/release/hands" \
  --tier T2
```

To require three successful repetitions of each selected task, use
`--repeat 3`. For example:

```sh
uv run --project ml python bench/live/run_live.py \
  --suite evals/live_t1.jsonl \
  --brain-url ws://127.0.0.1:8765 \
  --proxy-port 8790 \
  --hands-bin "$PWD/app/.build/release/hands" \
  --tier T1 --repeat 3
```

`pass^3` is reported only for cases with all three repetitions executed and
strictly passing. Add `--offline` to skip rows marked online. Use
`--include-manual` and `--include-pending` only when their fixture or feature is
available. Rows marked `requires_user_ok` remain skipped unless
`--allow-user-ok` is also supplied. `--dry-run` shows the resolved templates,
filters, and lifecycle order without starting HandsKit or contacting Brain.
`{{sandbox}}` resolves to `~/MuseletSandbox`; date templates use unpadded
`YYYY-M-D`, and `{{next_friday_ymd}}` means the strictly future Friday (seven
days ahead when the current day is Friday).

Stop the Brain process with Ctrl-C after the run. The runner always closes its
proxy and HandsKit subprocesses and removes the `~/MuseletSandbox` directory it
created. It refuses to replace an existing sandbox. Results, summary, command,
Git SHA, and HandsKit logs are written under `runs/bench/live/<timestamp>/`
unless `--out` selects another new directory.

## Context capture and implementation notes

Preconditions, restore reads, setup, teardown, and restore writes use injected
HandsKit script RPCs while no utterance is in flight. After setup, the runner
restarts HandsKit with `hands serve --utterance TEXT`; this captures the
frontmost app and focused element at the utterance boundary rather than
reusing context captured before setup.

The suite requires checks to be polled during execution while also requiring
script injection only between utterances. The runner resolves this conflict by
allowing only the declared check predicates to run during polling after the
first action; setup and teardown remain outside the utterance. Use read-only
checks for this phase. A missing `confirm_reply` is treated as unexpected,
fails the case, and is answered `false`.

The runner does not claim macOS benchmark results on Linux. `--dry-run` and the
fake-WebSocket tests validate suite planning and protocol behavior, not model
quality or live macOS execution.

The RPC safety guard is enabled by default and blocks message/email sends,
confirmation-risk skills, and invite-related scripts. Event cases are skipped
unless EventKit proves `Muselet Bench` is in a local source and is the default
for new events. `--setup-bench-calendar` creates it only in an existing local
source. `--no-safety-guard` disables these protections and labels the run
unsafe; use it only in a deliberately disposable benchmark environment.
