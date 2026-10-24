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
`hobbymac_score.py`; it preserves the upstream `completed` value and stores the
upstream run paths and scorer output beside `pass_final_state`, which is
recomputed with the same grader used for Muselet. The `completed` metric is
final-state success plus the system's reported success; `false_done` is a
reported success with a final-state failure. HobbyLM requires its own `.venv`,
model/runtime artifacts, and the macOS fixture setup. Older upstream event and
`none` rows do not include the complete before/after snapshots needed by the
independent grader, so those rows are conservatively marked as not verified.

The Muselet path requires macOS, Accessibility/Screen Recording permissions,
and a `hands` binary. It starts a benchmark Brain server by default and routes
HandsKit through the shared live-harness WebSocket proxy; `--external-brain`
uses an already-running server. First-action latency is measured on the wire
from the utterance frame to the first `act`/`skill` RPC, so it excludes client
startup and uses no BrainServer monkeypatch. The shared core polls and
evaluates the final-state grader, requires the reported outcome as well, and
records false-done and verified-completion latency. HobbyLM-native execution
continues to use the pinned upstream runner and scorer.

Event trials require `--allow-calendar` and the macOS default Calendar must be
the dedicated `Hobby Test` calendar. Event grading snapshots the test calendar
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

The current HandsKit `start_timer` skill is not implemented, so timer tasks are
reported as unverifiable failures instead of being counted from a success
message.

Run artifacts are written under `runs/bench/hobbylm/`. Do not use a personal
Calendar or run these desktop trials while another user is operating the Mac.
