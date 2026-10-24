# Native macOS vs Muselet UI: timers and feedback

Research only: no code changes yet. Everything here was researched from Linux (no Mac available), so all latency
figures are **to be measured** with the commands in the last section, and the platform behaviour cited from
Apple's docs is marked as either cited or unverified.

## 1. Clock.app timers, programmatically

The user wants timers in **Clock.app**, not in Muselet's internal `TimerRegistry`
(`app/Sources/HandsKit/Timers.swift`). Clock on macOS 27 supports named timers, a sound per timer, several
timers at once, and a "When timer ends → Stop Playing" option. Timers keep running across app switches and sleep
([Clock User Guide, macOS 27: Set timers](https://support.apple.com/guide/clock-mac/set-timers-apdw3d5aebf9/1.1/mac/27)).

| Route | Start | List | Cancel | Permissions | Reliability | Latency |
|---|---|---|---|---|---|---|
| **A. Shortcuts CLI** `shortcuts run "<name>"` with Clock actions | yes: *Start Timer* | partial: *Get Current Timer* returns the total or remaining time of **the current** timer | yes: *Cancel Timer* (plus *Pause* / *Resume*) | none new for Muselet: the `shortcuts` command runs the user's shortcut; the first run of a shortcut may ask for its own privacy grants (unverified for Clock actions) | high: Apple-supported CLI and first-party Clock actions | ~0.3–1 s expected (to measure) |
| B. App Intents directly | no public API to call another app's intents | — | — | — | n/a | — |
| C. URL scheme | none documented for Clock timers; `shortcuts://` URLs can run a shortcut but open the Shortcuts app | — | — | — | low | ~1 s plus an app switch |
| D. AX automation of Clock.app | yes: open the Timers tab, set the duration, press Start | yes: read the Timers tab (all timers) | yes: press Cancel on a row | Accessibility (already granted to Muselet) | medium-low: depends on UI layout, steals focus, breaks on redesigns | ~1–3 s (to measure) |

Evidence:
- **Shortcuts CLI.** Apple documents `shortcuts run "<name>"` with `-i` input and `-o` output, `shortcuts list`, `shortcuts view` and `shortcuts sign`. It recommends `shortcuts` over x-callback URLs, and says shortcuts that ask for input pause the CLI process. So the timer shortcut must take its duration as input instead of prompting ([Run shortcuts from the command line](https://support.apple.com/guide/shortcuts-mac/run-shortcuts-from-the-command-line-apd455c82f02/mac)).
- **Clock actions in Shortcuts.** Start Timer, Pause Timer, Resume Timer, Cancel Timer, Get Current Timer, and alarm and stopwatch actions ([shortcutactions.com, Clock](https://www.shortcutactions.com/actions/app/clock); third-party list, not verified on macOS 27). A Start Timer shortcut driven by "Shortcut Input" and run with `shortcuts run` works on macOS Ventura ([Apple StackExchange 453948](https://apple.stackexchange.com/questions/453948/macos-ventura-how-do-i-set-a-timer-in-clock-app-from-command-line)).
- **No import subcommand.** The `shortcuts` CLI has no `import` subcommand (only run, list, view, sign: [same CLI page](https://support.apple.com/guide/shortcuts-mac/run-shortcuts-from-the-command-line-apd455c82f02/mac)). Sharing works through an iCloud link, where the recipient clicks **Get Shortcut**, or through an exported file ([Share shortcuts](https://support.apple.com/guide/shortcuts-mac/share-shortcuts-apdf01f8c054/10.0/mac/27)). Signed files can be imported by "anyone" or by "people who know me" (`shortcuts sign --mode anyone|people-who-know-me`, CLI page). So **a bundled `.shortcut` cannot be installed silently**. It needs one user click in Shortcuts ("Add Shortcut" / "Get Shortcut"), done once during onboarding.
- **App Intents.** App Intents (macOS 13+) exposes *an app's own* actions to Siri, Spotlight and Shortcuts ([App Intents](https://developer.apple.com/documentation/appintents)). It is not a client API for calling Clock's intents. **AlarmKit**, Apple's alarm and countdown framework, lists iOS / iPadOS / Mac Catalyst 26 only, not macOS ([AlarmKit](https://developer.apple.com/documentation/alarmkit)). Even where it exists, it schedules alarms owned by the calling app, not timers in Clock.
- **URL scheme.** No Clock timer URL scheme appears in the Clock guide. Shortcuts URL schemes exist ([Intro to URL schemes](https://support.apple.com/guide/shortcuts-mac/intro-to-url-schemes-apd621a1ad7a/10.0/mac/27)), but Apple points CLI users to `shortcuts`.

**Recommendation: A, Shortcuts CLI**, with three bundled shortcuts installed once during onboarding:
```
Muselet Start Timer   input: "<seconds>|<label>"  -> Start Timer (duration from input)
Muselet Timer Status  -> Get Current Timer -> Stop and Output (remaining seconds)
Muselet Cancel Timer  -> Cancel Timer
```
- The brain runs `shortcuts run "Muselet Start Timer" -i <(echo 600)` through the existing `script shell` path, or as a native skill. Before use it checks that the shortcuts are installed with `shortcuts list`. If they are missing, it says one line ("Add the Muselet timer shortcuts once") and opens the iCloud link.
- **Listing:** Shortcuts only exposes *the current* timer. For "list my timers", Muselet keeps a record of the timers it started (label, fire time) and reconciles it with *Get Current Timer*. Use D (AX read of the Timers tab) only if the user asks about timers Muselet didn't start.
- **Fallback:** if Shortcuts is unavailable or the user declines the import, keep today's internal timer. AX (D) is not worth it as the primary path: it steals focus and is fragile.
- **Unverified (check on the Mac):**
  - latency of `shortcuts run` for each action;
  - which timer *Cancel Timer* and *Get Current Timer* target when several are running;
  - whether a Clock action prompts for permission on first run;
  - whether the label can be set through *Start Timer* (the Clock UI supports named timers).

## 2. Inventory: what Muselet draws that macOS already does

| Muselet UI today (code) | What macOS does natively | Recommendation | Why |
|---|---|---|---|
| **Timer done**: `Skills.startTimer` plays the `Glass` sound, posts a `UNUserNotificationCenter` notification "Timer done", and the mascot hops with a "Timer done: <label>" bubble (`AppDelegate.showTimerDone`) | Clock plays the per-timer sound and shows its own alert ([Set timers](https://support.apple.com/guide/clock-mac/set-timers-apdw3d5aebf9/1.1/mac/27)) | **Native** (Clock) once timers move to Clock. Keep the Muselet sound, notification and bubble only for the internal fallback timer | Two alerts for one timer is noise. Clock's alert can be snoozed and dismissed and survives Muselet restarts. |
| **Timer start reply**: mascot bubble "Timer set for 10 minutes" | Clock shows the countdown in its window and menu-bar widget | **Muselet** (short bubble) | The bubble is the voice reply that the command worked. AGENTS.md says replies are text in the bubble. |
| **Volume HUD**: `set_volume` / `change_volume` / `mute` run AppleScript `set volume output volume` (`AppleScript.swift`), then Muselet's `SkillHUD` glass panel | Media keys (`NX_KEYTYPE_SOUND_UP/DOWN/MUTE`, already in `MediaKeys.swift`) show the native volume OSD. The OSD steps are coarse (16 steps, per common macOS behaviour; unverified) | **Split**: relative "louder/quieter" and mute → post media keys and let the native OSD show, no SkillHUD. Absolute "set volume to 30" → AppleScript plus SkillHUD | Native OSD where macOS shows one. An AppleScript volume change shows no native OSD (inference from why SkillHUD was built; verify), so absolute changes still need feedback. |
| **Brightness HUD**: `set_brightness` via private `DisplayServicesSetBrightness`, then SkillHUD | Media keys `BRIGHTNESS_UP/DOWN` show the native brightness OSD | **Split**, same as volume | Same reasons. DisplayServices is private, so keep it only for absolute levels. |
| **Dark mode / Wi-Fi / Bluetooth HUD** (SkillHUD) | No OSD for these | **Muselet** (SkillHUD) | Nothing native to show. |
| **Reminders**: `create_reminder` via EventKit | Reminders.app owns the due-time alert | **Native** for the alert. Muselet only shows the one-line confirmation bubble | Already native, since EventKit items notify through Reminders. Never re-alert from Muselet. |
| **Events**: `create_event` via EventKit, `todays_agenda` | Calendar.app owns event alerts | **Native** alerts. Muselet bubble for the reply. A short text answer for the agenda | Same as reminders. |
| **Confirmations**: mascot `.confirm` bubble plus voice yes/no (`VoiceController`, `BubbleView`), sent back as `confirm_reply` | `NSAlert` / system dialogs (mouse-driven) | **Muselet** | Voice-first (push-to-talk "yes"). The CONFIRM gate must be harness-owned and logged (AGENTS.md design rules). A system dialog can't be answered by voice and isn't traced. |
| **Ghost cursor / element highlight** before acting | none | **Muselet** | Shows what the agent is about to touch; nothing native exists. |

## 3. Measure on the Mac (fills the "to measure" cells)

```bash
# one-time: install the three shortcuts (one click each), then:
shortcuts list | grep -i "^Muselet"
time shortcuts run "Muselet Start Timer" <<< "600"         # start latency
time shortcuts run "Muselet Timer Status"                  # list latency (current timer only)
time shortcuts run "Muselet Cancel Timer"                  # cancel latency
# two timers running: which one do Status/Cancel see?
# AX path for comparison: hands probe/observe on Clock.app Timers tab, time open + set + start
```
