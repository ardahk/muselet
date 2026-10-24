# HobbyLM benchmark tools

The full M5 Pro setup and benchmark sequence is in [`../RUNBOOK.md`](../RUNBOOK.md).

Before an eligible task is sent to the HobbyLM worker, the parent inventories
the document apps the task may touch. Existing windows/documents produce a
`user_documents_open` skip; an untrusted inventory produces
`user_documents_unverifiable`. The worker's Finder teardown closes only
case-created window IDs, never the front window. Re-run skipped tasks before
claiming a complete score. Terminal apps are deliberately excluded from the
registry, so terminal-driven changes remain a residual risk.

`upstream/PROVENANCE.md` records the vendored HobbyLM revision, Apache-2.0 license,
source links, and hashes. The frozen r1–r4 inputs are included unchanged.

## Plan and replay

```sh
uv run --project ml python bench/hobbylm/replay.py --dry-run --system muselet --round r4
uv run --project ml python bench/hobbylm/replay.py \
  --system hobbylm --round r4 --ids C01,C02 --repeats 2 --hobby-home /path/to/hobbylm
uv run --project ml python bench/hobbylm/replay.py \
  --system muselet --round r4 --ids C01,C02 --repeats 2 --hands-bin "$HANDS_BIN"
```

Set up and probe the isolated benchmark calendar on macOS before any event
trials:

```sh
uv run --project ml python -m bench.hobbylm.calendar_safety setup
uv run --project ml python -m bench.hobbylm.calendar_safety probe
```

The HobbyLM path runs the unchanged upstream `trial()` from a parent-clocked
worker, while the parent captures setup and pre-teardown state, polls with the
shared 500 ms interval, and applies the strict grader. Parent receipt timestamps
are authoritative; upstream latencies are stored only as
`agent_reported_*`. Upstream completion is informational and cannot override a
strict failure. Missing required snapshots are marked `ungradable` and excluded
from pass-rate denominators. The worker uses the pinned vendored harness and
the external HobbyLM `.venv`/model runtime. `hobbylm-published` is reference
only and intentionally cannot execute through this guarded harness.
The `hobbylm-published` reference path has no document guard and must not be
used for headline runs.

The Muselet path requires macOS, Accessibility/Screen Recording permissions,
and a `hands` binary. It starts a benchmark Brain server by default and routes
HandsKit through the shared live-harness WebSocket proxy; `--external-brain`
uses an already-running server. First-action latency is measured on the wire
from the utterance frame to the first `act`/`skill` RPC, so it excludes client
startup and uses no BrainServer monkeypatch. The shared core polls and
evaluates the final-state grader; the agent's own outcome claim is retained
only as `reported_success`/`false_done`.

Muselet calculator trials disclose a setup choice that mirrors HobbyLM's
harness: Calculator is opened, cleared with Escape, and verified at Display 0
before the utterance. Timer trials grade successful `start_timer` RPC results
captured by the proxy (or use catalogued `list_timers` when available); without
catalogued `cancel_timers`, the record discloses that created timers remain scheduled.

Event trials run only when EventKit proves `Muselet Bench` is in a local source
and is the default for new events. Otherwise they are recorded as skipped with
`bench calendar not local default`. `--setup-bench-calendar` creates the named
calendar only in an existing local source and refuses iCloud/Exchange fallback.
Event grading snapshots the test calendar
with EventKit from one day before to 400 days after the trial, then diffs by
event identifier; teardown removes only events added in that diff. Expected
event starts use HobbyLM's `plan_event` in `Asia/Kolkata`. Because HobbyLM test
mode creates events with `with_invite=False`, its person check is adapted to
verify the expected person in the created event's title, notes, or attendees
rather than requiring an invitation. Screenshot grading compares image files
in the directory reported by `defaults read com.apple.screencapture location`
(or `~/Desktop`) before and after the utterance and removes new files during
teardown; it does not trust RPC-returned paths. A `none` task passes only when
no `act`/`skill` RPC was dispatched and the relevant device, app, Finder,
screenshot, and Calendar state is unchanged.

The proxy guard is enabled by default. It blocks message/email sending,
catalog skills requiring confirmation, invite-related scripts, and event
arguments containing attendees or email addresses. HobbyLM native
Mail/Messages/send/invite helpers raise and record `safety_blocked`; confirmation
replies are always `false`.

Run artifacts are written under `runs/bench/hobbylm/`. Do not use a personal
Calendar or run these desktop trials while another user is operating the Mac.
