# Timers in the Clock app

Muselet starts timers in the macOS **Clock** app through shortcuts that you create once in
**Shortcuts**. Muselet can't install a shortcut by itself. Until the shortcut exists (or when
Settings › Timers › "Use the Clock app for timers" is off), Muselet runs its own timer instead,
just as before.

Steps marked *(unverified on macOS 27)* use action or field names that haven't been checked on
macOS 27 yet. If a name differs, search the action list for the word in bold.

## 1. Required: "Muselet Start Timer"

1. Open **Shortcuts** (Settings › Timers › Set up › Open Shortcuts, or Spotlight: "Shortcuts").
2. Click **+** in the toolbar to make a new shortcut.
3. Click the title at the top and rename the shortcut to exactly `Muselet Start Timer`.
   Capitals and spaces matter.
4. Open the shortcut's details (the **ⓘ** button in the right sidebar) and turn on
   **Use as Quick Action** / **Receive input**. Set the input type to **Text** only.
   *(unverified on macOS 27)* In some versions, the editor shows a "Receive **Text** input
   from **Nowhere**" block at the top instead. Set it to **Text**, and leave the source as
   is: `shortcuts run` input always reaches the shortcut.
5. In the action search field (right sidebar), type **Get Numbers from Input** and
   double-click it. Its input should read **Shortcut Input**. If it doesn't, click the blue
   field and choose **Shortcut Input**.
6. Search for **Start Timer** (Clock) and double-click it. *(unverified on macOS 27: the action
   may be named "Start Timer" under **Clock**.)*
7. In the Start Timer action:
   - click the duration number and choose the magic variable **Numbers** (from step 5);
   - click the unit and choose **seconds**. Muselet always sends whole seconds, for example
     `600` for 10 minutes.
8. Close the editor window. Shortcuts saves automatically.

Check it from Terminal (optional):

```sh
echo 10 > /tmp/t.txt && /usr/bin/shortcuts run "Muselet Start Timer" --input-path /tmp/t.txt
```

Clock should show a 10-second timer.

## 2. Optional: "Muselet Cancel Timer"

Lets "cancel the timer" stop a Clock timer. Without it, Muselet reports `unsupported` for Clock
timers.

1. Make a new shortcut and name it exactly `Muselet Cancel Timer`.
2. Add **Cancel Timer** (Clock). *(unverified on macOS 27: the action may be listed as "Stop
   Timer".)*
3. It takes no input.

## 3. Optional: "Muselet Timer Status"

Lets Muselet compare its list of timers with what Clock is actually counting down.

1. Make a new shortcut and name it exactly `Muselet Timer Status`.
2. Add **Get Current Timer** (Clock). *(unverified on macOS 27)*
3. Add **Stop and Output** and set its output to the timer's **remaining time**. Muselet reads
   plain seconds (`598`), `m:ss` / `h:mm:ss`, or text like `9 minutes 58 seconds`. Empty
   output or `0` means no timer. *(unverified on macOS 27: you may need a **Get Details of
   Timer › Remaining Time** action between the two.)*

## 4. Back in Muselet

Open Settings › Timers and click **Check again**. The badge changes to **Clock ready**.
Muselet looks for the shortcuts with `shortcuts list` and caches the result for 60 s. A
shortcut that you just added is picked up on the next timer request.

## How it works (for developers)

- `start_timer` (HandsKit `Skills.startTimer`): when the toggle is on and `Muselet Start Timer`
  is installed, Muselet writes the seconds to a temp file and runs
  `/usr/bin/shortcuts run "Muselet Start Timer" --input-path <file>` with `Process`. There is no
  shell, no AppleScript, and a 10 s timeout. On success it returns
  `{backend:"clock", seconds, label, ms, fires_at, timer_id}`.
- Fallbacks return `{backend:"muselet", fallback_reason, ...}`. The fallback reasons are:
  `shortcut_missing`, `shortcut_timeout`, `shortcut_exit_<n>`, `shortcuts_unavailable`,
  `input_file_failed`, and `clock_off` (the toggle is off).
- Muselet keeps its own record of every timer, on both backends. That record feeds the
  `timers` RPC and the `$TMPDIR/muselet-timers/<pid>.json` snapshot that `hands probe timers`
  and bench/hobbylm read. Each item has a `backend` field. A Clock record never rings in
  Muselet: Clock rings.
- `timers {clock_status?}` merges those records with `Muselet Timer Status`. Clock reports
  only its current timer, so records are never dropped. Clock records get `clock_seen`, and the
  reply's `clock` field reports `status` (`unavailable` / `none` / `running` / `unknown`).
- `timers_cancel` runs `Muselet Cancel Timer` for Clock timers. Without that shortcut it
  returns `unsupported: ...` and keeps the record.
- `timer_backend {refresh?}` returns
  `{clock_ready, shortcuts, enabled, backend, cancel_ready, status_ready}`.
  `hands probe timers` includes the same object under `backend`.
