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
- **Instant commands** ("volume 30", "dark mode", "turn off Wi-Fi"): one on-device forward pass picks the skill (52 ms p50
  on our earlier r2 router); first action p50 193 ms in our live suite.
- **Anything else** ("open Safari, search flights to Tokyo"): a local planner reads the macOS accessibility tree,
  streams small action batches, and starts acting before it finishes thinking. For chained tasks we choose
  intelligence over latency: a step may take a few seconds (ship gate: per-step p50 <= 3 s) if that raises the pass rate. Steps carry `expect` checks against
  the live accessibility tree.
- **Messages and Gmail**: "text Sam I'll be there in ten" fills the message and waits for a spoken yes; "draft a
  reply in Gmail" reads the open email and leaves a draft.
- **Follow-ups**: after "navigate to Wikipedia", "search for history" searches Wikipedia, not Google. TBD(PR #50 merge)
- **Timers in Clock**: "set a timer for ten minutes" starts it in the Clock app.
- **Finance, offline.** "Prep me for my meeting with the Hendersons" reads Calendar, the client folder, the
  portfolio in Numbers and last meeting's notes, then writes a brief to Notes and highlights the sheet: $118,151.60
  to rebalance, $30,825.00 harvestable losses (VXUS blocked by a wash sale until 2026-11-11), $61,400.00 Roth
  room. "Reconcile my receipts" OCRs 8 receipts on-device (Apple Vision, in
  parallel), matches 6, flags a transposed-digit total and one receipt with no
  transaction. Every number comes from deterministic code with evidence; the model never does arithmetic.
- **Premiere Pro** shortcuts: "cut here", "add a marker", "export".
- It **asks** when a request is ambiguous, hands low-confidence picks to the planner instead of acting, and
  **confirms** before sending, deleting, buying or running shell scripts.

## How we built it
- **App (Swift)**: menu-bar app, push-to-talk CGEventTap, FluidAudio Parakeet TDT v2 on the Neural Engine,
  mascot + ghost-cursor overlay. **HandsKit** executes: native skill > AX action > keys > pixel click, with a fused
  act-and-observe RPC and `expect` predicates.
- **Brain (Python, MLX)**: loopback WebSocket to the app. **Router**: Qwen3.5-4B with a LoRA we trained on Tinker
  (about 38k route + 25k argument examples for iteration 2, soft labels from Qwen3.6-35B-A3B; about $136 of Tinker
  compute in total across all training). The option list lives
  in a cached static prefix, so each request costs only its own tokens; we read the answer distribution after a
  `choice#` prefill from one forward pass. **Planner** (local Qwen3.5-4B, greedy): AX text in, a 5-action DSL out, plus one BM25-retrieved solved example,
  which lifted held-out pass rates from .643 / .667 / .400 to .714 / .750 / .462 for about 70 ms more TTFT.
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

## Accomplishments that we're proud of
- Our trained router picks the right action for .913 of 103 clean held-out requests, vs .767 for the same base
  model untrained.
- Live on the Mac, graded by final state: 19/22 single-command tasks and 1/5 multi-step tasks (27 of 43 cases
  ran), first action p50 193 ms. TBD(live suite re-run)
- TBD(HobbyLM r4 replay)/125 on HobbyLM's sealed live set vs their published 90/125.
- TBD(DeskMind diag)/39 on DeskMind Bench, same Mac.
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
