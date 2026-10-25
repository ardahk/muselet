# Muselet: hold a key, say it, it's done. On your Mac, offline.

Every number is sourced in `claims.md`. `TBD(<run>)`: fill from that run or delete the sentence before publishing.

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
- **Instant commands** ("volume 30", "dark mode", "turn off Wi-Fi"): one on-device forward pass of our trained
  router picks the OS-level skill (60 ms route p50); first action p50 193 ms in our live suite (earlier config).
- **Apps, operated like a person would**: "set a timer for two minutes", "remind me to call mom at 5", "open Notes and
  write a template about my day". The router hands app tasks to a local planner that reads the macOS accessibility
  tree, acts, and checks the result each step. A rule-based "finish when" check stops the task as soon as the goal is
  on screen: the Clock countdown is running, the reminder is in the list.
- **The web, in your own browser**: "play some jazz on YouTube" types into YouTube's own search box in the same tab of
  your default browser and stops once the Pause button shows. "Add some chicken to my cart" adds exactly one item and
  never checks out. With a Gmail email open, "reply saying I can do Thursday at three" writes the draft and leaves it
  unsent.
- **Two local planners**: a 4B model we fine-tuned plans normal tasks at ~0.3 s per step; Qwen3.6-35B-A3B (a mixture of
  experts with ~3B active) takes over for websites, open-ended asks, and screens the accessibility tree can't see.
- **Finance, offline.** "Prep me for my meeting with the Hendersons" reads Calendar, the client folder, the
  portfolio in Numbers and last meeting's notes, then writes a brief to Notes and highlights the sheet: $118,151.60
  to rebalance, $30,825.00 harvestable losses (VXUS blocked by a wash sale until 2026-11-11), $61,400.00 Roth
  room. "Reconcile my receipts" OCRs 8 receipts on-device (Apple Vision, in
  parallel), matches 6, flags a transposed-digit total and one receipt with no
  transaction. Every number comes from deterministic code with evidence; the model never does arithmetic.
- **Premiere Pro**: "cut here", "add a marker", "export" (keyboard shortcuts; the timeline is not in the accessibility tree).
- It **asks** when a request is ambiguous, **confirms** before sending, deleting, buying or posting (and before
  shell scripts or AppleScript that clicks UI), and **refuses** requests like "erase every file in my Documents
  folder".

## How we built it
- **App (Swift)**: menu-bar app, push-to-talk CGEventTap, FluidAudio Parakeet TDT v2 on the Neural Engine,
  mascot + ghost-cursor overlay. **HandsKit** executes: native skill > AX action > keys > pixel click, with a fused
  act-and-observe RPC and `expect` predicates.
- **Brain (Python, MLX)**: loopback WebSocket to the app. **Router**: Qwen3.5-4B with a LoRA we trained on Tinker
  (about 38k route + 25k argument examples for iteration 2, soft labels from Qwen3.6-35B-A3B; all training under the $150 Tinker cap,
  TBD(console total)). The option list lives
  in a cached static prefix, so each request costs only its own tokens; we read the answer distribution after a
  `choice#` prefill from one forward pass. **Planner**: AX text in, a 5-action DSL out, plus one BM25-retrieved solved example. A Qwen3.5-4B LoRA we
  fine-tuned on Tinker scores .857 / 1.000 / .692 on our three held-out planner sets (mean .850, vs .770 for the base
  4B with thinking) at ~0.3 s per step. Qwen3.6-35B-A3B with a 512-token thinking budget is the planner for web,
  open-ended and AX-blind tasks. **Finish rules** (`finish.py`) turn each goal into an observable end state, so the
  agent stops as soon as it can see the goal (Pause button, cart count +1, Clock countdown).
- **Brain tools**: whole workflows (`finance_review`, `advisor_prep`) are catalog skills the router picks in one
  pass; stdlib `Decimal` engines compute, AppleScript writes to Numbers and Notes in one call each. Tests match
  fixture truth files to the cent.
- **Evals**: strict final-state graders. We rerun HobbyLM and DeskMind on our own Mac with their harnesses.

## Challenges we ran into
- Byte-identical prompt rendering between Tinker training and the MLX runtime (token-level parity file).
- More options than single-token ids: a custom id alphabet (`A-Z 0-9 b d e ...`), each id one token.
- The Premiere timeline is not in the accessibility tree; we drive it with shortcuts and a UXP bridge.
- Making a 4B model safe with money: it may only phrase; any digit, `$` or `%` in its text is rejected.
- Honest evals: 37 of our 140 router test cases turned out to have near-duplicates in the training data; we
  quote only the 103 clean ones, and run competitor benchmarks only with a router that has 0 overlap with them.
- Live testing safely on a real machine: the runner checks each case's precondition mechanically and skips if the
  screen is locked or a user document is open.
- A real mistake: a mis-aimed pixel click removed a Spotify playlist from the user's library during testing. Pixel
  clicks are now refused in Spotify and gated in every app that holds user data; UI-scripting AppleScript needs a yes.

## Accomplishments that we're proud of
- Our trained router (it3) picks the right action for .945 of route_v2 and .922 of 103 clean route_v1 requests
  (base model untrained: .767 on route_v1), with calibrated confidence (ECE .018).
- Live on the Mac, graded by final state: 19/22 single-command tasks and 1/5 multi-step tasks (27 of 43 cases
  ran), first action p50 193 ms. TBD(live suite re-run)
- Competitor benchmarks, honestly: we have no valid comparable HobbyLM score yet, and on DeskMind's decision
  benchmarks their 4B is ahead of our decisions LoRA (JevBench .831 vs .779, typed-decisions .658 vs .622).
- A full advisor meeting prep with Wi-Fi off in TBD(rehearsal) s.

## What we learned
Speed comes from not generating: one forward pass for routing, deterministic code for anything with a right
answer, and a planner, allowed to think, only for chained tasks where getting it right matters more than milliseconds. Trust comes from checks you can read:
`expect` predicates against the live UI while it runs, and final-state grading in our evals.

## What's next
Check the goal state before every `done`, gate Send in every chat app, ship the grounder for apps
the AX tree cannot see, more brain tools (expense reports, invoice matching), Google
Sheets and Excel, and an advisor CRM connector that still never leaves the device.

## Built with
Swift, SwiftUI, AppKit, Accessibility API, ScreenCaptureKit, Apple Vision, Core ML, FluidAudio (Parakeet TDT v2),
Python 3.12, MLX / mlx-lm, Qwen3.5-4B, Tinker, tinker-cookbook, AppleScript, Apple Numbers, Notes, Calendar,
Adobe Premiere Pro (UXP), WebSockets.
