# Muselet: hold a key, say it, it's done. On your Mac, offline.

Every `{{...}}` is defined in `claims.md`; fill from the named run or delete the sentence before publishing.

## Inspiration
Voice assistants on the Mac either talk instead of doing (they explain where the menu is) or ship your screen to
a cloud model. [Clicky](https://github.com/farzaa/clicky) showed how good a voice buddy next to your cursor feels, but it
streams audio to AssemblyAI and a screenshot to Claude through a proxy. For financial advisors,
[Savvy Intelligence](https://www.savvywealth.com/savvy-intelligence) shows meeting prep can be automated, but
as a platform you join, running on AI model providers (under zero data retention). We
wanted an agent that **actually does the work**, **as fast as a keyboard shortcut**, with **nothing leaving the Mac**.

## What it does
Hold Right Option and talk. A small mascot answers in a speech bubble, a ghost cursor flies to each target before
it acts, and the Mac does the thing.
- **Instant commands** ("volume 30", "dark mode", "turn off Wi-Fi"): one on-device forward pass picks the skill in
  `{{route_ms_p50}}` ms; release to action in `{{instant_e2e_ms_p50}}` ms.
- **Anything else** ("open Safari, search flights to Tokyo"): a local planner reads the macOS accessibility tree,
  streams small action batches, and starts acting before it finishes thinking. Steps carry `expect` checks against
  the live accessibility tree.
- **Finance, offline.** "Prep me for my meeting with the Hendersons" reads Calendar, the client folder, the
  portfolio in Numbers and last meeting's notes, then writes a brief to Notes and highlights the sheet: $118,151.60
  to rebalance, $30,825.00 harvestable losses (VXUS blocked by a wash sale until 2026-11-11), $61,400.00 Roth
  room. "Reconcile my receipts" OCRs 8 receipts on-device (Apple Vision, in
  parallel), matches 6, flags a transposed-digit total and one receipt with no
  transaction. Every number comes from deterministic code with evidence; the model never does arithmetic.
- **Premiere Pro**: "cut here", "add a marker", "export".
- It **asks** when a request is ambiguous, hands low-confidence picks to the planner instead of acting, and
  **confirms** before sending, deleting, buying or running shell scripts.

## How we built it
- **App (Swift)**: menu-bar app, push-to-talk CGEventTap, FluidAudio Parakeet TDT v2 on the Neural Engine,
  mascot + ghost-cursor overlay. **HandsKit** executes: native skill > AX action > keys > pixel click, with a fused
  act-and-observe RPC and `expect` predicates.
- **Brain (Python, MLX)**: loopback WebSocket to the app. **Router**: Qwen3.5-4B with a LoRA we trained on Tinker
  (`{{train_examples}}` examples, soft labels from a larger teacher, `{{tinker_usd}}` spent). The option list lives
  in a cached static prefix, so each request costs only its own tokens; we read the answer distribution after a
  `choice#` prefill from one forward pass. **Planner** (`{{planner_model}}`): AX text in, a 5-action DSL out.
- **Brain tools**: whole workflows (`finance_review`, `advisor_prep`) are catalog skills the router picks in one
  pass; stdlib `Decimal` engines compute, AppleScript writes to Numbers and Notes in one call each. Tests match
  fixture truth files to the cent.
- **Evals**: strict final-state graders. We rerun HobbyLM and DeskMind on our own Mac with their harnesses.

## Challenges we ran into
- Byte-identical prompt rendering between Tinker training and the MLX runtime (token-level parity file).
- More options than single-token ids: a custom id alphabet (`A-Z 0-9 b d e ...`), each id one token.
- The Premiere timeline is not in the accessibility tree; we drive it with shortcuts and a UXP bridge.
- Making a 4B model safe with money: it may only phrase; any digit, `$` or `%` in its text is rejected.

## Accomplishments that we're proud of
- `{{hobby_muselet_pass}}`/125 on HobbyLM's sealed live set vs HobbyLM's `{{hobby_rerun_pass}}`/125, same Mac.
- `{{dm_muselet_strict}}`/39 on DeskMind Bench, `{{dm_muselet_false_done}}` false "done", step p50
  `{{dm_muselet_step_p50_s}}` s.
- A full advisor meeting prep in `{{advisor_prep_s}}` s with Wi-Fi off.
- `{{live_t1_pass}}`/43 live on-Mac tasks graded by final state, `{{live_false_done}}` false "done".

## What we learned
Speed comes from not generating: one forward pass for routing, deterministic code for anything with a right
answer, and a planner only for the long tail. Trust comes from checks you can read:
`expect` predicates against the live UI while it runs, and final-state grading in our evals.

## What's next
Check the goal state before every `done`, gate Send in every chat app, ship the grounder for apps
the AX tree cannot see, more brain tools (expense reports, invoice matching), Google
Sheets and Excel, and an advisor CRM connector that still never leaves the device.

## Built with
Swift, SwiftUI, AppKit, Accessibility API, ScreenCaptureKit, Apple Vision, Core ML, FluidAudio (Parakeet TDT v2),
Python 3.12, MLX / mlx-lm, Qwen3.5-4B, Tinker, tinker-cookbook, AppleScript, Apple Numbers, Notes, Calendar,
Adobe Premiere Pro (UXP), WebSockets.
