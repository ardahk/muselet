# 3:00 demo script

Setup before the take: `evals/fixtures/advisor/setup_mac.sh --apply` and
`evals/fixtures/finance/setup_mac.sh --apply` (statement, budget and 8 receipts into `~/Documents/Finance`);
Premiere project with a sequence open, default keymap; Chrome open; Numbers/Notes closed; Muselet panel top-right.
Open items: `claims.md` §4. Every number spoken is a fixture fact
(`evals/fixtures/*`, PR tests) or a filled `{{placeholder}}`; drop any unfilled one. Say only the safety wording
marked "allowed" in `claims.md` §2.

| Time | Spoken (presenter / mascot bubble) | On screen | Agent does | Fallback line if it fails |
|---|---|---|---|---|
| 0:00-0:06 | "This is Muselet. I hold one key and talk. Everything runs on this Mac." | Desktop, mascot idle, panel | – | – |
| 0:06-0:10 | "Volume thirty." / bubble "Volume 30." | Skill HUD volume bar; latency chip by the bubble | `set_volume level=30` | "Routing's live, the HUD just lags." |
| 0:10-0:14 | "Dark mode." / "Dark mode on." | HUD "Dark Mode On", screen flips, chip | `dark_mode on=true` | "It's in the trace; let's keep moving." |
| 0:14-0:20 | "That chip is release to first action: `{{instant_e2e_ms_p50}}` ms. Deciding takes `{{route_ms_p50}}`. One forward pass." | Zoom on chip | – | Chip missing: "one forward pass, on-device." |
| 0:20-0:24 | "Open Chrome and find flights to Tokyo next Friday." | Chrome front | router -> MULTI_STEP -> planner loop | – |
| 0:24-0:44 | Presenter: "It reads the accessibility tree, starts acting while the planner is still decoding, and checks each step against the page." | Ghost cursor to address bar, types, results | streamed batch: `keys cmd+l`, `type … enter`, `expect title~"Tokyo"` -> `verify` | "It replans on a failed check; here's a finished run from earlier." (cut to backup clip) |
| 0:44-0:50 | Mascot: planner's `done` summary (e.g. "Flights to Tokyo are up.") | Results page, chip `{{browser_task_s}}` | `done` alone in a batch, after a passing `expect` or fresh observe | – |
| 0:50-0:56 | "Wi-Fi off." / "Wi-Fi off." | HUD "Wi-Fi Off", menu-bar icon off | `wifi on=false` | Click it off by hand: "same result." |
| 0:56-1:00 | "Now I'm a financial advisor. Prep me for my meeting with the Hendersons." | Mascot thinking | router -> `advisor_prep` (brain tool, no planner) | – |
| 1:00-1:22 | Bubbles: "Checking your calendar for the Hendersons..." -> "Review Mon Oct 26, 10:00, per the client file." -> "Reading the Hendersons' portfolio..." -> "Running the numbers on this Mac..." -> "Writing the brief in Notes..." Presenter: "Calendar, their folder, the portfolio, last meeting's notes. No upload." | Calendar -> Finder -> Numbers: opportunity rows highlighted, Review sheet | `prep()` in `Decimal`; highlight + review + note AppleScripts | "It's deterministic; here's the brief it wrote in rehearsal." (open the note) |
| 1:22-1:34 | Mascot: "5 opportunities found. Brief is in Notes." Presenter: "$118,151.60 to rebalance, $30,825 of losses to harvest, and it caught a wash sale: VXUS was bought in the IRA 12 days ago. Every number is code, with evidence." | Notes brief, chip `{{advisor_prep_s}}` | – | Read the numbers off the brief. |
| 1:34-1:38 | "Reconcile my receipts." | Mascot thinking | router -> `finance_review task=receipts` | – |
| 1:38-1:54 | Bubbles: "Reading your statement..." -> "Matching receipts to the statement..." -> "Writing results to Numbers..." Mascot: "6 receipts match, 1 receipt mismatch, 1 unmatched." Presenter: "Receipt 7 has swapped digits; receipt 8 has no charge." | Statement in Numbers, rows marked, chip `{{receipts_s}}` | 8 `ocr` RPCs in parallel (Apple Vision), `Decimal` matching with evidence, rows written | "OCR's on-device; here's the reconciled sheet." (switch to the rehearsal copy) |
| 1:54-2:00 | "Still offline. Client data never left the laptop." | Zoom on Wi-Fi icon | – | – |
| 2:00-2:06 | "Switch to Premiere. Cut here." | Premiere timeline | `premiere_command razor_at_playhead` -> cmd+k | "Premiere hides its timeline from accessibility; we use its shortcuts." |
| 2:06-2:14 | "Add a marker." / "Marker added." | Marker at playhead | `premiere_command add_marker` -> m | – |
| 2:14-2:30 | "Export." / "Export dialog open." | Export dialog | `premiere_command export` -> cmd+m | "Export starts from the same dialog; we stop here for time." |
| 2:30-2:45 | "Results. HobbyLM's sealed live set: `{{hobby_muselet_pass}}` of 125, vs `{{hobby_rerun_pass}}` for HobbyLM on this Mac. DeskMind Bench: `{{dm_muselet_strict}}` of 39, `{{dm_muselet_step_p50_s}}` s per step." | Benchmark slide (`video_shotlist.md` shot 9) | – | If not run: "We're rerunning both on this Mac; harness is in the repo." |
| 2:45-3:00 | "Clicky sends your screen to a cloud model. Savvy runs on cloud model providers. Muselet does the work, on your Mac, with Wi-Fi off. Hold a key, say it, it's done." | Mascot "success", Wi-Fi icon off | – | – |

Q&A crib (2 min):
- *Does it confirm everything irreversible?* "It confirms risky skills, send/delete/buy buttons, shell scripts and
  scripts that click or run code. Send in chat apps other than Messages, Mail and Slack isn't gated yet."
- *Does it verify "done"?* "Steps with an `expect` are checked live and a failed check replans. It won't call a
  task done without a passing check or a fresh look at the screen. A goal-level check is next; our benchmark
  numbers are graded on final state."
- DeskMind already reports 39/39 on its bench, so our claim there is speed at equal strictness, on the same Mac.
- Premiere UXP bridge is untested; the demo uses default shortcuts. Numbers: `claims.md`.
