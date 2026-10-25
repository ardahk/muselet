# Timers in the Clock app

With Settings › Timers › **Use the Clock app for timers** on, Muselet first drives the
macOS **Clock** app directly through Accessibility. This does not require a shortcut. If
Accessibility or the Clock UI is unavailable, Muselet tries the optional
**Muselet Start Timer** shortcut, then falls back to a Muselet timer. With the toggle off,
Muselet uses its own timer. A successful direct Clock start leaves Clock frontmost.

## Direct Clock setup and probe

Allow Muselet under **System Settings › Privacy & Security › Accessibility**. Settings › Timers
shows whether direct Accessibility or the shortcut backup is ready. The direct path also
requires Clock to be installed.

Use the read-only probe to inspect Clock's Accessibility tree and timer controls:

```sh
hands probe clock
```

If Clock is not running, the probe prints a hint. `hands probe clock --open` opens Clock and
selects the **Timers** tab if needed, then prints the same tree, parsed wheels, controls,
values, settable attributes, and AX actions. It never presses Start or Cancel and never changes
the timer wheels. The probe requires Accessibility permission.

## Optional backup: "Muselet Start Timer"

This shortcut is used only if the direct AX attempt fails before pressing Start. Muselet can't
install shortcuts by itself.

1. Open **Shortcuts** (Settings › Timers › Set up › Open Shortcuts, or Spotlight: "Shortcuts").
2. Click **+** in the toolbar to make a new shortcut.
3. Click the title at the top and rename the shortcut to exactly `Muselet Start Timer`.
   Capitals and spaces matter.
4. Open the shortcut's details (the **ⓘ** button in the right sidebar) and turn on
   **Use as Quick Action** / **Receive input**. Set the input type to **Text** only.
   *(Unverified on macOS 27.)* In some versions, the editor shows a "Receive **Text** input
   from **Nowhere**" block at the top instead. Set it to **Text**, and leave the source as
   is: `shortcuts run` input always reaches the shortcut.
5. In the action search field (right sidebar), type **Get Numbers from Input** and
   double-click it. Its input should read **Shortcut Input**. If it doesn't, click the blue
   field and choose **Shortcut Input**.
6. Search for **Start Timer** (Clock) and double-click it. *(Unverified on macOS 27: the action
   may be named "Start Timer" under **Clock**.)*
7. In the Start Timer action:
   - click the duration number and choose the magic variable **Numbers** (from step 5);
   - click the unit and choose **seconds**. Muselet sends whole seconds, for example `600`
     for 10 minutes.
8. Close the editor window. Shortcuts saves automatically.

Check the backup from Terminal (optional):

```sh
echo 10 > /tmp/t.txt && /usr/bin/shortcuts run "Muselet Start Timer" --input-path /tmp/t.txt
```

Clock should show a 10-second timer.

## Optional backup shortcuts

**Muselet Cancel Timer** is tried if AX cancellation of a direct Clock timer fails:

1. Make a new shortcut and name it exactly `Muselet Cancel Timer`.
2. Add **Cancel Timer** (Clock). *(Unverified on macOS 27: the action may be listed as
   "Stop Timer".)*
3. It takes no input.

**Muselet Timer Status** lets Muselet compare shortcut-started timers with Clock's current
countdown:

1. Make a new shortcut and name it exactly `Muselet Timer Status`.
2. Add **Get Current Timer** (Clock). *(Unverified on macOS 27.)*
3. Add **Stop and Output** and set its output to the timer's **remaining time**. Muselet reads
   plain seconds (`598`), `m:ss` / `h:mm:ss`, or text like `9 minutes 58 seconds`. Empty
   output or `0` means no timer. *(Unverified on macOS 27: you may need a **Get Details of
   Timer › Remaining Time** action between the two.)*

## How it works (for developers)

- With the toggle on, `start_timer` tries the Clock AX lane, then
  `/usr/bin/shortcuts run "Muselet Start Timer" --input-path <file>`, then Muselet's internal
  timer. The shortcut receives whole seconds through a temporary file; no shell or AppleScript
  is used, and the shortcut run has a 10 s timeout. Toggle off skips both Clock paths.
- Direct AX failures before Start include `clock_ax_unavailable`, `screen_locked`,
  `duration_out_of_range`, `clock_launch_failed`, `clock_not_frontmost`, `clock_no_window`,
  `timers_tab_missing`, `timers_tab_failed`, `picker_missing`,
  `wheel_h|m|s_unreadable|stuck|mismatch`, `start_missing`, `start_disabled`,
  `wheels_changed`, and `start_press_failed`. These are returned as `clock_ax_reason` when a
  later backend starts the timer.
- Shortcut fallback reasons are `shortcut_missing`, `input_file_failed`, `shortcut_timeout`,
  `shortcuts_unavailable`, and `shortcut_exit_<n>`. `clock_off` means the toggle is off. Muselet
  fallback results include `fallback_reason`; when AX was attempted they also include
  `clock_ax_reason`.
- Direct AX success returns a `clock_ax` record with `verified` and optional `verify_signal`,
  `wheel_method`, and `label_set`. A timeout after pressing Start remains a `clock_ax` result
  with `verified:false` and **never falls back**; falling back could start a duplicate timer.
  The timer record is kept for both Clock backends, but Clock timers never fire in Muselet.
- `timers {clock_status?}` keeps every record. Shortcut-started Clock records are merged with
  `Muselet Timer Status`; direct AX records are observed through Accessibility. AX observation
  is included as `clock_ax:{status,running}` when requested or when an AX timer is recorded.
  A successful read matches records with `clock_seen` and `clock_left_s`. AX read statuses are
  `unavailable`, `not_running`, `no_window`, `tab_hidden`, and `read`.
- `timers_cancel {id?}` cancels Muselet records internally. It tries the Clock AX Cancel
  control for `clock_ax` records, then the optional `Muselet Cancel Timer` shortcut. If neither
  can cancel the timer, it returns `unsupported`, keeps the record, and includes
  `clock_ax_reasons` for failed AX attempts. Shortcut-started Clock records use the Cancel
  shortcut.
- `timer_backend {refresh?}` returns
  `{clock_ready, clock_ax_ready, shortcuts, enabled, backend, cancel_ready, status_ready}`.
  `backend` is the selected `clock_ax`, `clock`, or `muselet` path. `hands probe timers`
  includes the readiness object under `backend`.

The Clock Accessibility tree, timer wheel value formats/actions, label editability, and running
timer structure are heuristic and have not been verified against a live macOS 27 Clock UI here.
Use `hands probe clock` on the target Mac before changing those assumptions.
