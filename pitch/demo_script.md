# 3:00 demo script

Setup before the take: `evals/fixtures/advisor/setup_mac.sh --apply`; budget `budget_oct2026.xlsx` open in
Numbers; receipts in `~/Downloads/receipts`; Premiere project with a sequence open; Chrome open; Numbers/Notes
closed except the budget; Muselet panel visible top-right. Prerequisites: `claims.md` §4. Every number spoken is
either a fixture fact (`evals/fixtures/*`) or a filled `{{placeholder}}`; drop any unfilled one.

| Time | Spoken (presenter / mascot bubble) | On screen | Agent does | Fallback line if it fails |
|---|---|---|---|---|
| 0:00-0:06 | "This is Muselet. I hold one key and talk. Everything runs on this Mac." | Desktop, mascot idle, panel | – | – |
| 0:06-0:10 | "Volume thirty." / bubble "Volume 30." | Latency readout, volume HUD | `set_volume level=30` | "Routing's live, the HUD just lags." |
| 0:10-0:14 | "Dark mode." / "Dark mode on." | Whole screen flips | `dark_mode on=true` | "It's in the trace; let's keep moving." |
| 0:14-0:20 | "That's `{{route_ms_p50}}` milliseconds to decide, `{{instant_e2e_ms_p50}}` to act. One forward pass." | Readout zoom | – | Say only "one forward pass, on-device." |
| 0:20-0:24 | "Open Chrome and find flights to Tokyo next Friday." | Chrome front | router -> MULTI_STEP -> planner | – |
| 0:24-0:44 | Mascot: "Searching flights to Tokyo." Presenter: "It reads the accessibility tree, not pixels, and starts clicking before it's done thinking." | Ghost cursor to address bar, types, results | `open`, `keys cmd+l`, `type ... enter`, `expect title~"Tokyo"` | "The planner retries a different path; here's a finished run from earlier." (cut to backup clip) |
| 0:44-0:50 | Mascot: "Flights to Tokyo are up." | Results page | `done` after verify | – |
| 0:50-0:56 | "Wi-Fi off." / "Wi-Fi off." | Menu-bar Wi-Fi icon goes empty | `wifi on=false` | Click it off by hand: "same result." |
| 0:56-1:00 | "Now I'm a financial advisor. Prep me for my meeting with the Hendersons." | Mascot thinking | router -> `advisor_prep` | – |
| 1:00-1:22 | Mascot: "Henderson review Monday ten. Pulling their file." Presenter: "Calendar, their folder, the portfolio, last meeting's notes. No upload." | Calendar -> Finder -> Numbers: BND and VNQ rows go green, VXUS amber; Review sheet | `prep()`; highlight + review + note scripts (DEMO.md) | "Workflow is deterministic; here's the brief it wrote in rehearsal." (open the note) |
| 1:22-1:34 | Mascot: "Brief's in Notes. Four opportunities." Presenter: "$118,151.60 to rebalance, $30,825 of losses to harvest, and it caught a wash sale: VXUS was bought in the IRA 12 days ago. Every number is code, with evidence." | Notes brief | – | Read the numbers off the brief. |
| 1:34-1:38 | "Reconcile my receipts." | Numbers budget sheet | router -> `finance_review task=receipts` | – |
| 1:38-1:54 | Mascot: "6 matched. Receipt 7 has swapped digits. Receipt 8: no charge." | Rows flagged in sheet | Apple Vision OCR x8, `reconcile_receipts`, color rows | "OCR's on-device; here's the reconciled sheet." (switch to the Review copy) |
| 1:54-2:00 | "Still offline. Client data never left the laptop." | Zoom on Wi-Fi icon | – | – |
| 2:00-2:06 | "Switch to Premiere. Cut here." | Premiere timeline | `premiere_command razor_at_playhead` (cmd+k) | "Premiere hides its timeline from accessibility; we use its shortcuts." |
| 2:06-2:14 | "Add a marker." / "Marker added." | Marker appears at playhead | `premiere_command add_marker` (m) | – |
| 2:14-2:30 | "Export." / "Export dialog open." | Export dialog | `premiere_command export` (cmd+m) | "Export starts from the same dialog; we stop here for time." |
| 2:30-2:45 | "Results. HobbyLM's sealed live set: `{{hobby_muselet_pass}}` of 125, vs `{{hobby_rerun_pass}}` for HobbyLM on this Mac. DeskMind Bench: `{{dm_muselet_strict}}` of 39, `{{dm_muselet_step_p50_s}}` s per step." | Benchmark slide (`video_shotlist.md` shot 9) | – | If not run: "We're rerunning both on this Mac; harness is in the repo." |
| 2:45-3:00 | "Clicky sends your screen to a cloud model. Savvy runs on cloud model providers. Muselet does the work, on your Mac, with Wi-Fi off. Hold a key, say it, it's done." | Mascot "success", Wi-Fi icon off | – | – |

Q&A crib (2 min): DeskMind already reports 39/39 on its bench, so our claim there is speed at equal strictness,
on the same Mac. Premiere UXP bridge is untested; the demo uses shortcuts. Numbers: `claims.md`.
