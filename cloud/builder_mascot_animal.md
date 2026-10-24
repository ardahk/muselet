# Cloud builder: mascot-animal, a cute animal pet with the same behaviour — Muselet (Swift UI)

Repo `ardahk/muselet`. Read `AGENTS.md` (product decisions; no TTS, bubble <= 12 words) and the current mascot:
`app/Sources/MuseletApp/Mascot/` (`MascotView.swift`, `+Build`, `+Moods`, `+Life`, `+Effects`, `MascotPaths.swift`,
`MascotController.swift`, `BubbleView.swift`, `PillView.swift`). Branch `cloud/mascot-animal` from main, one PR.
You can't compile Swift on Linux. Write carefully against the existing APIs; the lead's team compiles and fixes on
the Mac. Keep the diff inside `app/Sources/MuseletApp/Mascot/` (plus tests if you add pure helpers).

## What the user said
"Create me a mascot that is an animal. I don't like how this mascot looks, but I like all the interactions,
and I liked how we took good inspo from GPT." Keep every interaction and mood. Replace only the character art.

## The character: a round, chubby kitten ("Muse")
- **Silhouette:** one soft rounded head-body blob, slightly wider than tall, sitting.
  - two triangular ears with rounded tips and pink inner ears;
  - small paws peeking out at the bottom;
  - a tail curling around one side.
- **Palette:** warm cream body; ginger patches on the ears, crown and tail tip; pink inner ears and nose; soft
  blush cheeks. It should read on both light and dark wallpapers, so add a 1 pt warm-brown outline at low alpha.
- **Face:**
  - big glossy eyes: dark, with two white highlights;
  - a tiny triangle nose;
  - a "w" mouth that can open into a small "o";
  - three whisker lines per side, very thin.
- **Size:** keep the current mascot frame and anchor points, so the bubble, pill, ghost cursor and hover
  hit-areas still line up.

## Moods: same names and triggers as today (`MascotView+Moods.swift`)
- **idle:**
  - breathing (scale 1.00 -> 1.03, 3 s);
  - random blinks every 3–6 s, about 15% of them double blinks;
  - an ear twitch every 6–12 s;
  - a slow tail sway (±8°, 4 s);
  - an occasional look-around every 8–15 s.
- **hover:** hop, ears perk up, eyes grow, and the tail flicks up. Hovering wakes a sleeping cat.
- **listening:**
  - ears fully up and rotated toward the screen centre;
  - eyes wide;
  - tail up with the tip curled;
  - the existing pulse ring and micLevel ring.
- **thinking:**
  - eyes look up-left;
  - one paw raised to the chin (a simple paw shape moving up);
  - the existing three bobbing dots.
- **acting:** lean toward the action, using the existing `look(atCG:)` gaze; the tail swishes.
- **success:** hop, happy closed "^ ^" eyes, sparkles (existing), and a brief tail wag.
- **confused:**
  - head tilt;
  - one ear down;
  - the "?" (existing);
  - the mouth turns into a small wavy line.
- **sleeping:**
  - curled pose: body lowered, tail wrapped over the paws;
  - closed eyes, slow breathing, zZ (existing);
  - keep the 5-minute timer.

## Rules
- Every animation needs a Reduce Motion variant: static poses, no hops or loops. Re-apply it on
  `accessibilityDisplayOptionsDidChangeNotification` like today.
- Core Animation layers and paths, as today. No image assets or third-party libraries.
- Keep the public surface `MascotController` / `MascotView` uses: same method names and mood enum, so
  `AppDelegate`, `PillController` and `BubbleView` need no changes.
- Put the shape geometry in one place (`MascotPaths.swift`) with named constants, so a different animal (fox,
  red panda, otter) can be swapped in later by changing that file plus colours.

Report in the PR body: files changed, a state-by-state description (what each mood looks like) so the lead can
screenshot-check it, and anything you were unsure about in the existing APIs.
