# HobbyLM benchmark tools

`upstream/PROVENANCE.md` records the vendored HobbyLM revision, Apache-2.0 license,
source links, and hashes. The frozen r1–r4 inputs are included unchanged.

## Plan and replay

```sh
python3 bench/hobbylm/replay.py --dry-run --system muselet --round r4
HOBBY_HOME=/path/to/hobbylm python3 bench/hobbylm/replay.py \
  --system hobbylm --round r4 --ids C01,C02 --repeats 2
python3 bench/hobbylm/replay.py \
  --system muselet --round r4 --ids C01,C02 --repeats 2
```

The HobbyLM path invokes the pinned upstream `hobbymac_run.py` and
`hobbymac_score.py`; it stores the upstream run paths and scorer output beside
the strict-completion and independently recomputed final-state results. HobbyLM
requires its own `.venv`, model/runtime artifacts, and the macOS fixture setup.

The Muselet path requires macOS, Accessibility/Screen Recording permissions,
and `hands` on `PATH`. It starts and tears down a benchmark-instrumented local
Brain server by default. `--external-brain` connects to an already-running
server, but cannot report first-action latency. The default first-action timer
uses `time.monotonic()` from just before the `hands serve` process is launched
to the benchmark hook immediately before the first `act`/`skill` RPC dispatch;
this includes client startup. Completion latency is the first observed final
state satisfying the task grader. The grader checks the final OS state and does
not treat the Brain's outcome as proof of success.

Event trials require `--allow-calendar` and the macOS default Calendar must be
the dedicated `Hobby Test` calendar. Created test events are read back and
removed during teardown. Screenshot files are checked and removed. The current
HandsKit `start_timer` skill is not implemented, so timer tasks are reported as
unverifiable failures instead of being counted from a success message.

Run artifacts are written under `runs/bench/hobbylm/`. Do not use a personal
Calendar or run these desktop trials while another user is operating the Mac.
