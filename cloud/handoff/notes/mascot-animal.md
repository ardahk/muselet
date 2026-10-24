## Handoff
_Last updated: 2026-10-24 cut-over (lane: mascot-animal, brief: `cloud/builder_mascot_animal.md`)_

**State**
- Done: the kitten mascot "Muse" is merged to `main` via PR #36.
  - Code commit: `238db23`. Handoff-notes commit: `4b7d95a`. Merge: `(none found; squash or fast-forward)`. Current `main`: `0e7b5a8`.
- Verified on Linux only:
  - `swiftc -parse` (Swift 6.4.1) is clean on all 7 mascot files.
  - Type-check against hand-written AppKit/QuartzCore stubs is clean.
- Not verified:
  - Has never been compiled with the macOS SDK, and the app has never run.
  - No Mac build or screenshot result has been reported back to this lane.
- In flight: nothing. No running jobs.
- Not started: any follow-up (art tweaks, fixes from a Mac build). None has been requested.

**Resume steps**
1. Branch from main: `git fetch origin && git checkout -b cloud/mascot-animal-<topic> origin/main`.
2. On a Mac: `cd app && swift build`, then `swift run MuseletApp`. Fix any SDK-only errors, keeping them inside `app/Sources/MuseletApp/Mascot/`.
3. Screenshot each mood against the PR #36 checklist: https://github.com/ardahk/muselet/pull/36
   - The moods are idle, hover, listening, thinking, acting, success, confused, sleeping, plus Reduce Motion.
   - Check that the additive rotations (ear twitch, tail sway/flick/wag) compose with each pose.
4. Art tweaks are constants only:
   - geometry and pose numbers in `MascotPaths.swift`;
   - colours in `MascotPalette.swift`.
5. Optional Linux checks:
   - Install Swift via swiftly (https://www.swift.org/install/linux/).
   - Run `swiftc -parse app/Sources/MuseletApp/Mascot/{MascotPaths,MascotPalette,MascotView,MascotView+Build,MascotView+Moods,MascotView+Life,MascotView+Effects}.swift`.
   - For a stub type-check: copy the files, swap `import AppKit` / `import QuartzCore` for a stub file, and stub `Brand.tint`, `MascotMood` and `OverlayCanvas.setScale`. The original stubs are gone with the old VM.

**Artifacts**
- Commits: `238db23` (code), `4b7d95a` (notes), `(none found; squash or fast-forward)` (merge). This note is on branch `cloud/mascot-animal-handoff`.
- PR: https://github.com/ardahk/muselet/pull/36 (merged).
- No HF repos, Tinker runs/checkpoints or run dirs: this lane has no ML work.
- The preview-image script (`~/mascot-preview/render.py`) and the stubs (`~/mascot-typecheck/`) were on the old VM only. Neither is needed to resume.

**Spend so far**
- No HF, Tinker, OpenAI or Anthropic usage.
- Devin compute: one session in the old org.

**Open questions for the lead**
- Did the Mac build pass, and is the art right (proportions, ginger amount, 0.45 outline alpha)?
- The listening ears aim at the screen centre only when the mood is applied, not live while the mascot is dragged. Is that OK?

**Gotchas**
- Keep `MascotView.size` / `bodySize` / `bodyBase` (108×116 / 56×54 / (54,16)). The bubble, pill, ghost cursor and hit areas depend on them.
- Keep `MascotPaths.bodyPath(width:height:bottomRadius:topRadius:)`. `App/Theme.swift` (`MenuBarIcon`) uses it.
- `MascotPaths.Mouth.open(_:)` was removed. The mic level drives `setMouthOpen(_:)` on the separate `mouthOpen` layer.
- Accessory effects (rings, dots, ?, sparkles) still use `Brand.tint` from `App/Theme.swift`.
- Every new animation is guarded by `reduceMotion`. The `accessibilityDisplayOptionsDidChangeNotification` handler resets `breathKind` and `tailKind`, then re-applies the mood.
