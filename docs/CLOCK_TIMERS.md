# Timers in the Clock app

`start_timer` drives the macOS **Clock** app directly through Accessibility (`clock_ax`). There is
no setting and no Shortcuts involvement. If Accessibility or the Clock UI is unavailable, Muselet
silently starts its own timer instead (`muselet`; bubble + sound + notification when it fires).
A successful Clock start leaves Clock frontmost.

## Setup and probe

Allow Muselet under **System Settings › Privacy & Security › Accessibility** (the menu-bar panel
lists it while it is missing). Clock must be installed.

Use the read-only probe to inspect Clock's Accessibility tree and timer controls:

```sh
hands probe clock
```

If Clock is not running, the probe prints a hint. `hands probe clock --open` opens Clock and
selects the **Timers** tab if needed, then prints the same tree, parsed wheels, controls,
values, settable attributes, and AX actions. It never presses Start or Cancel and never changes
the timer wheels. The probe requires Accessibility permission.

## How it works (for developers)

- `start_timer` tries the Clock AX lane, then Muselet's internal timer.
- AX failures before Start: `clock_ax_unavailable`, `screen_locked`,
  `duration_out_of_range`, `clock_launch_failed`, `clock_not_frontmost`, `clock_no_window`,
  `timers_tab_missing`, `timers_tab_failed`, `picker_missing`,
  `wheel_h|m|s_unreadable|stuck|mismatch`, `start_missing`, `start_disabled`,
  `wheels_changed`, and `start_press_failed`. After Start, an unverified result uses
  `start_unverified`. The Muselet fallback result carries the reason as both `fallback_reason`
  and `clock_ax_reason`.
- A Clock start is verified only by `running_added` or `pause_cancel` from a sane Timers-tab AX
  tree within 2 seconds. If the first verification window times out, Start is retried once only
  when the Timers UI is present and clearly unchanged: Start is enabled, picker Cancel is disabled,
  the running count is unchanged, and no new Pause appeared. If it remains unverified, Muselet
  starts its own timer with `verified:false` and both `fallback_reason` and `clock_ax_reason` set to
  `start_unverified`. The result includes `clock_ax_steps` with the AX progress and verification
  trace. A Clock start that registers after the verification window could duplicate the Muselet
  timer. Verified Clock starts return `backend:"clock_ax"` with `verified:true`, a
  `verify_signal`, and `clock_ax_steps`; `clock_ax` timers ring in Clock, not Muselet.
- Replies distinguish a verified Clock start (`Timer set in Clock for 10 minutes`) from a Muselet
  fallback (`Timer set for 10 minutes in Muselet`); other timer results use `Timer set for 10 minutes`.
- Every timer keeps a record in Muselet's registry (and the `hands probe timers` snapshot).
- `timers {clock_status?}` returns `{timers, backend}` and keeps every record. AX observation is
  included as `clock_ax:{status,running}` when requested or when a `clock_ax` timer is recorded;
  a successful read matches records with `clock_seen` and `clock_left_s`. AX read statuses are
  `unavailable`, `not_running`, `no_window`, `tab_hidden`, and `read`.
- `timers_cancel {id?}` cancels Muselet timers internally and presses Clock's Cancel control
  for `clock_ax` records. If that fails it returns `unsupported`, keeps the record, and includes
  `clock_ax_reasons`.
- `timer_backend {}` returns `{clock_ax_ready, backend}` with `backend` = `clock_ax` or
  `muselet`. `hands probe timers` includes it under `backend`.

The Clock Accessibility tree, timer wheel value formats/actions, label editability, and running
timer structure are heuristic and have not been verified against a live macOS 27 Clock UI here.
Use `hands probe clock` on the target Mac before changing those assumptions.
