
## Your lane: `ux` — the Mac app experience and demo appeal
Files: `app/Sources/MuseletApp/*` (menu bar, panel, mascot, speech bubble, ghost cursor overlay, push-to-talk,
STT, permissions onboarding, brain connection states), `app/scripts/`, plus the `ui`/`say`/`confirm` messages
the brain sends (`ml/src/brain/server.py`, `orchestrator.py`).
The `hands` lane reviews this code for correctness; you review it as a product. Judges will see a live
3-minute demo; the bar is "feels like Apple shipped it" (reference: Clicky, github.com/farzaa/clicky, and
heyclicky's UI). Product rules: voice input only (hold Right Option), no text-to-speech, mascot replies in a
speech bubble with <= 12 words, ghost cursor shows where the agent acts while the real cursor stays with the
user.
Look hardest at:
- Time to first feedback: from key-down to the mascot visibly listening, from release to "thinking", and
  from decision to the ghost cursor moving. Anything that makes the agent feel slow even when it is fast.
- State machine gaps: every brain state (listening, thinking, acting, success, confused, awaiting confirm,
  disconnected, brain not running, permission missing) must have a clear visual and text; no stuck states
  after cancel, errors or reconnects.
- macOS-native feel: materials/vibrancy, SF Symbols, system fonts and spacing, Dark/Light mode, multiple
  displays, full-screen Spaces, Reduce Motion, overlay never stealing focus or clicks.
- First-run and permissions onboarding (Accessibility, Microphone, Screen Recording, Automation): clear,
  short, recoverable, and never blocks the demo flow once granted.
- Bubble copy: short, friendly, specific ("Opened Downloads", not "Done"); errors that tell the user what
  to do next; confirm prompts that name the exact object (recipient, file, amount).
- Demo polish opportunities with high payoff and low effort (e.g. a visible latency readout, a mascot
  reaction when offline mode works). Rank them; effort estimates in hours.
