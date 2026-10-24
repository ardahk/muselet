# W6: App UI: kitten mascot, polished panel, Settings behind the gear

Repo `ardahk/muselet`. Read `docs/HANDOFF.md` and `cloud/builder_mascot_animal.md` (the full art + mood spec).

## State
- **Merged (PR #24):** the pet-style interactions:
  - breathing, random blinks, look-around, hover hop;
  - mood animations (listening/thinking/acting/success/confused/sleeping);
  - the floating mic/keyboard pill;
  - a vibrancy bubble;
  - a clean menu-bar panel: status dot, "Hold right ⌥ to talk", last request + result, 3 example prompts;
  - Settings behind the gear: Permissions incl. Contacts and Automation, Models incl. the 35B fallback toggle
    for Macs with ≥ 48 GB, Voice, Debug.
- **The user liked the interactions but not the character.** `cloud/mascot-animal` (Swift, uncompiled) is
  redrawing it as a round kitten with the same moods.

## Steps
1. When `cloud/mascot-animal` has a PR:
   - on the Mac, run `cd app && swift build && swift test --scratch-path .build-hands` and fix compile errors
     minimally;
   - `bash app/scripts/build_app.sh`;
   - quit and relaunch Muselet: check the app log `~/Library/Logs/Muselet/muselet.log` for an in-flight request
     first.
2. **Screenshot every mood** using the debug hooks (`app/scripts/debug_ui.sh`, `DebugHooks.swift`):
   - capture with `screencapture -x -R<x,y,w,h>` cropped to the mascot;
   - check Reduce Motion;
   - check light and dark wallpaper legibility.
   Post the images to the user.
3. **Polish list:**
   - the bubble never overlaps the pill;
   - the latency chip is readable;
   - the panel example prompts run against the previously frontmost app (fixed: `sendFromPanel`);
   - the mascot doesn't cover the Dock;
   - sleeping after 5 min;
   - waking on hover.

## Acceptance
User sign-off on the screenshots; no regressions in voice / confirm flows (`VoiceController`, confirm bubble
yes/no).
