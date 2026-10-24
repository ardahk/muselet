## Handoff
_Last updated: 2026-10-24 ~21:05 UTC (lane: mascot-animal, brief: `cloud/builder_mascot_animal.md`)_

**State**
- Done: the kitten "Muse" is implemented in `app/Sources/MuseletApp/Mascot/` (7 files: `MascotPaths`, new `MascotPalette`, `MascotView`, `+Build`, `+Moods`, `+Life`, `+Effects`). It is committed, pushed, and PR #36 is open against `main`.
- Verified on Linux only:
  - `swiftc -parse` (Swift 6.4.1) is clean on all 7 files.
  - Type-check against hand-written AppKit/QuartzCore stubs is clean.
  - Not compiled with the macOS SDK; the app has never run.
- In flight: nothing. Waiting for the lead's Mac build and screenshot check. The repo has no CI checks.

**Exact next steps**
1. Lead or Mac team: `cd app && swift build`, then fix any SDK-only errors. They should stay within `Mascot/`.
2. Screenshot each mood against the checklist in the PR body. Check that the additive rotations (ear twitch, tail sway/flick/wag) compose correctly with each pose.
3. Apply the lead's feedback on `cloud/mascot-animal` and push to PR #36. Update this section and `cloud/handoff/notes/mascot-animal.md`.

**Artifacts**
- Branch `cloud/mascot-animal`. The code commit is `238db23`; the HANDOFF commit sits on top of it.
- PR: https://github.com/ardahk/muselet/pull/36
- No HF repos, Tinker runs or checkpoints: this lane has no ML work.
- Off-repo files on the original VM (lost if the session dies):
  - `~/mascot-preview/render.py`: Python→SVG mock of the paths; it produced the PR preview image.
  - `~/mascot-typecheck/`: stubs plus `typecheck.sh`.
  - Swift toolchain in `~/swift`.

**Spend so far**
- No HF, Tinker, OpenAI or Anthropic usage.
- Devin compute: this one session only.

**Open questions for the lead**
- Is the art right (proportions, ginger amount, outline alpha)? Tweaks are constants in `MascotPaths.swift` / `MascotPalette.swift`.
- The listening ears aim at the screen centre only when the mood is applied, not live while dragging. Is that OK?

**Gotchas**
- Keep `MascotView.size` / `bodySize` / `bodyBase` (108×116 / 56×54 / (54,16)). The bubble, pill, ghost cursor and hit areas depend on them.
- Keep `MascotPaths.bodyPath(width:height:bottomRadius:topRadius:)`. `App/Theme.swift` (`MenuBarIcon`) uses it.
- `MascotPaths.Mouth.open(_:)` was removed. The mic level now drives `setMouthOpen(_:)` on the separate `mouthOpen` layer.
- To rebuild the Linux checks, install Swift via swiftly. Then:
  - `swiftc -parse` the 7 files;
  - for the stub type-check, copy the files, replace `import AppKit` / `import QuartzCore` with a stub module, and stub `Brand.tint`, `MascotMood` and `OverlayCanvas.setScale`.
