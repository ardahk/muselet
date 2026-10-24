# Cloud builder: app UI redesign (mascot + menu-bar panel + settings) — Muselet

Repo `ardahk/muselet`. Read `AGENTS.md` first. SwiftUI/AppKit in `app/Sources/MuseletApp/` only (Mascot/, Panel/,
App/, Overlay/). Don't edit HandsKit, the brain or the protocol except where stated. Branch `cloud/app-ui` from main, one
PR. Linux can't compile Swift: write careful, conservative Swift 6 / macOS 27 SwiftUI with no new dependencies, keep each
file small, and list every API you used. A local agent compiles it, fixes anything that doesn't build, and takes
screenshots for the user.

## What the user wants (their words)
"make the bot somewhat like chatgpt's pet. cute, it moves etc." "the page that shows up when you click the menu bar icon
should be nice looking, and settings should be hidden under a settings icon. rn it is designed more for testing."
Their reference is the ChatGPT desktop pet: a small pixel-art cloud character with a terminal face, floating above a
capsule pill that has a pencil (type) button and a waveform (voice) button.

## 1. Mascot (keep the potato character's identity, or propose a cuter one, but ship ONE polished design)
- Idle life: breathing (scale 1.00↔1.03, 3 s), blinks every 3–6 s at random, an occasional small look-around. On hover,
  it perks up.
- Moods mapped from AppModel.mood:
  - listening: ears/eyes up, plus a soft pulse ring driven by micLevel;
  - thinking: eyes look up, three-dot bob;
  - acting: leans toward the ghost cursor target (look(atCG:) exists);
  - success: hop plus sparkle;
  - confused: head tilt plus "?";
  - sleeping: zZ after 5 idle minutes (the timer exists).
- Under the mascot, a floating capsule pill (like the reference) with a mic button (push-to-talk alternative: click to
  start/stop listening) and a keyboard button (opens a small text field to type a request, sent as a normal utterance
  frame with final:true). The pill appears on hover and while listening; otherwise only the mascot shows.
- Draggable as today; respect reduced motion (NSWorkspace accessibilityDisplayShouldReduceMotion).
- Bubble: rounded, vibrancy material, max 12 words, latency chip as today.

## 2. Menu-bar panel (clean, product-like)
- Header: mascot icon, "Muselet", a status dot (Connected / Offline).
- Main view, simple: "Hold right ⌥ to talk", the last request and its result, and 3 example prompts the user can click
  (they run as utterances).
- A gear button opens Settings (sheet or a second page). Move everything technical there:
  - Permissions, the current rows (Automation grants included);
  - Models: a "Use 35B planner fallback (needs ≥ 48 GB RAM)" toggle, shown only when hw.memsize ≥ 48 GB. Persist it
    in UserDefaults and send `{"t":"config","escalate_planner":true|false}` to the brain on change and on every
    (re)connect; show the `config_ack` result ("Loaded" / reason);
  - Voice (STT engine, readiness);
  - Debug: the activity log, Reconnect, Reset mascot, Quit.
- Native look: SF Symbols, system materials, 13 pt system font, adapts to dark/light mode.

## 3. Deliver
The PR, a list of every SwiftUI/AppKit API used, and screenshots-by-description of each state so the local agent can
check them.
