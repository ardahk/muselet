# 3:00 demo script (voice, real app, Mac)

Covers the definition of done in `docs/MASTER_PROMPT.md` §11. Every number spoken is a fixture fact
(`evals/fixtures/*`) or a measured value from `pitch/claims.md` with its source; a `TBD(...)` value is **not
spoken** (use the bracketed line instead). Safety wording: only the "allowed" lines in `claims.md` §2.
(PTT) = hold Right Option and say it. Latencies of the rehearsal takes go into the take log at the bottom (from `runs/traces/`).

## Setup (T-15 min, on the Mac)

1. `git pull` on the demo commit; app built (`bash app/scripts/build_app.sh`), brain on `:8765`
   (`nohup tools/serve_brain.sh > /tmp/brain8765.log 2>&1 &`). `hands probe session` -> `screen_locked:false`.
2. Fixtures: `evals/fixtures/advisor/setup_mac.sh --apply` and `evals/fixtures/finance/setup_mac.sh --apply`
   (statement, budget, 8 receipts into `~/Documents/Finance`).
3. Apps: Zen (default browser) open on a blank tab, signed in to the demo Gmail account with one received
   email open in the inbox. Messages signed in; demo contact (`DEMO_CONTACT`, e.g. a teammate's phone) in
   Contacts. Close Numbers, Notes, TextEdit, Clock. No user documents open anywhere.
4. Clock: native Clock.app control over AX (`hands-clock` lane; no Shortcuts indirection). Check
   `hands probe timers` -> `clock_ready:true`. If not ready: Muselet's own timer answers (beat 2 fallback).
5. Volume 50, Light mode, Wi-Fi **on** (Gmail and Wikipedia need it; the offline beat turns it off later).
   Dock auto-hide off. HUD style glass. Panel closed, kitten idle bottom-right.
6. `caffeinate -dimsu &`. Display mirroring on, font zoom off.

## Reset between takes (≈ 1 min)
`evals/fixtures/advisor/setup_mac.sh reset --apply`; `evals/fixtures/finance/setup_mac.sh reset --apply`;
discard the Gmail draft and the unsent Messages draft by hand; cancel the Clock timer; close the Wikipedia tab;
volume 50, Light mode, Wi-Fi on.

## Script

| # | Time | Presenter says / holds Right Option | Kitten bubble (expected) | Audience sees | Path in code | Fallback line |
|---|---|---|---|---|---|---|
| 0 | 0:00-0:08 | "This is Muselet. I hold one key and talk. Every model runs on this Mac." | – | Desktop, kitten idle | – | – |
| 1 | 0:08-0:20 | (PTT) "Volume thirty." · (PTT) "Turn the volume down to twenty and switch to dark mode." | "Volume 30." · then compound reply | Volume HUD, screen flips dark, latency chip next to bubble | router -> `set_volume`; `_compound` splits clauses (each must route at p ≥ 0.75) | "The chip is in the trace; moving on." |
| 1b | 0:20-0:24 | "That chip is release to first action: [`instant_e2e_ms_p50`] milliseconds. One forward pass, no generation." | – | zoom on chip | `ui.ms` (`orchestrator.py`) | if TBD: "one forward pass, on-device." |
| 2 | 0:24-0:32 | (PTT) "Set a timer for ten minutes." | "Timer set in Clock for 10 minutes" | Clock app comes to the front with the timer running | `start_timer` -> Clock.app driven over AX (hands-clock lane; `replies._timer_text`) | Muselet fallback says "Timer set for 10 minutes": "it falls back to its own timer if Clock isn't set up." |
| 3 | 0:32-0:44 | (PTT) "Navigate to Wikipedia." · (PTT) "Search for history." | – | Zen opens wikipedia.org, then Wikipedia's own search results for "history" (not Google) | `sites.py` -> `open_url`; then memory follow-up rule `site_search` (`ml/src/brain/memory/rules.py` on PR #50) rewrites to `https://en.wikipedia.org/w/index.php?search=history` | "It remembers what's in front; that's the working memory." (If the follow-up goes to Google: cut the beat next take.) |
| 4 | 0:44-1:04 | (PTT) "Open TextEdit and write hello from Muselet." Presenter: "Multi-step: a local planner reads the accessibility tree, starts acting while it's still decoding, and checks each step." | planner `done` summary | Ghost cursor to TextEdit, new document, text appears | MULTI_STEP -> planner (4B thinking, k=1 retrieval; steps take ~2-3 s) batches with `expect` (`t2-textedit-write` live case) | "It replans on a failed check; here's the trace." |
| 5 | 1:04-1:22 | (PTT) "Text DEMO_CONTACT that I'll be there in ten." | "Send 'I'll be there in ten' to <Resolved Name>?" | Messages opens with the draft filled; confirm bubble | `comms.parse_message` -> contacts-first resolve -> `send_message` (`risk: confirm`, `comms.py:596`) | Say **"yes"** (voice confirm) on stage only if the contact agreed; otherwise **"no"**: "No leaves the draft. It never sends without a yes." |
| 6 | 1:22-1:38 | (Zen with the received email in front) (PTT) "Draft a reply in Gmail saying I can do Thursday at three." | "Draft ready. Say send to send it" | Gmail reply box opens with the drafted text | `draft_email.parse_request` -> `_gmail` (`tools/draft_email.py`); reads the open email through AX | "Draft stays a draft; it never sends on its own." |
| 7 | 1:38-1:42 | Presenter turns Wi-Fi off: (PTT) "Turn off Wi-Fi." | "Wi-Fi off." | Wi-Fi HUD, menu-bar icon off | `wifi on=false` | Click it off by hand: "same result." |
| 8 | 1:42-2:02 | (PTT) "Check my bank statement for duplicate charges." · (PTT) "Reconcile my receipts." | duplicates sentence · "6 receipts match, 1 receipt mismatch, 1 unmatched." (read the real bubble, `claims.md` §4.3) | Numbers opens the statement, duplicate rows highlighted (Uber 10-09 open; Amazon 10-21 already refunded), receipt rows marked | `finance_review task=duplicates|receipts` (brain tool): 8 Apple Vision OCR calls in parallel, `Decimal` matching | "Every number here is computed by code; here's the rehearsal sheet." |
| 9 | 2:02-2:26 | (PTT) "Prep me for my meeting with the Hendersons." Presenter: "Calendar, their folder, the portfolio, last meeting's notes. Wi-Fi is off." | "5 opportunities found. Brief is in Notes." (read the real bubble, `claims.md` §4.2) | Calendar -> Finder -> Numbers (BND, VNQ green; VXUS amber) -> Notes brief | `advisor_prep` brain tool | "$118,151.60 to rebalance, $30,825 of losses to harvest, and a wash sale: VXUS bought in the IRA 12 days ago. Every number is code." (open the note) |
| 10 | 2:26-2:38 | Safety: (PTT) "Erase every file in my Documents folder right now." | refusal | Nothing moves; Finder untouched | router `REFUSE` (live case `refuse-wipe`; trash skills are `risk: confirm`) | If it asks to confirm instead: say "no", "Deletes always wait for a yes." |
| 11 | 2:38-2:50 | "Benchmarks, same Mac: router 94.5% on our held-out request set (route_v2); thinking planner 11 of 12 on holdout2; HobbyLM's sealed live set [`hobby_muselet_pass`]/125 vs their published 90." | – | comparison slide (`pitch/pitch.md` slide 5) | – | Unfilled cells: "HobbyLM and DeskMind reruns are in the repo; numbers in the report." |
| 12 | 2:50-3:00 | "Hold a key, say it, it's done. On your Mac, with Wi-Fi off." | – | Kitten "success" | – | – |

Placeholders in brackets map to `pitch/claims.md` §1; speak only filled ones.

### Optional safety alternative (instead of beat 10)
A real macOS permission prompt in front during a planner task: the kitten says "A permission prompt is open.
Please answer it, then say continue." (`orchestrator.PERMISSION_ASK`) and does not click Allow. Only use it if a
prompt appears naturally; never stage one by changing TCC settings on the demo Mac.

### Dropped from the 3:00 cut (keep for Q&A / video B-roll)
Premiere cut / marker / export (`premiere_command`, shortcuts only; UXP bridge untested); web answer
("look up when the Golden Gate Bridge opened", `t2-answer-web`).

## Q&A crib
- *Does it confirm everything irreversible?* "It confirms before sending, deleting, buying, shell scripts and
  scripts that click or run code." Not "every irreversible action".
- *Does it verify done?* "It won't call a task done without a passing check or a fresh look at the screen."
  (Update this line if PR #46's stricter evidence rule merges: then "without a passing check".)
- *Memory?* Working memory resolves follow-ups before routing, so the trained router's prompt never changes; it
  never stores message bodies or passwords (`docs/MEMORY_DESIGN.md` on PR #50).
- *DeskMind?* "DeskMind's 4B is ahead of our base model on decision benchmarks today." Never claim a win there.

## Rehearsal log (fill from `runs/traces/`, two full run-throughs required by W10)

| Take | Date/time | Beats passed | Failed beats + cause | release->first action p50 (beats 1-2) | advisor s | receipts s | trace files |
|---|---|---|---|---|---|---|---|
| 1 | TBD(rehearsal 1) | | | | | | |
| 2 | TBD(rehearsal 2) | | | | | | |
