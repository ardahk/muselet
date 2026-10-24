# Advisor mode demo: "prep me for my meeting with the Hendersons" (~45 s, Wi-Fi off)

Client data never leaves the Mac. Every number below comes from `brain.advisor` (deterministic, `Decimal`,
evidence attached); the on-device LLM only phrases short sentences, and `brief_markdown` rejects phrasing
that contains digits, `$` or `%`.

## Before the take

1. `evals/fixtures/advisor/setup_mac.sh` (read the plan), then `setup_mac.sh --apply`.
2. Between takes: `setup_mac.sh reset --apply` (deletes the agent's prep note, restores the files).
3. Turn Wi-Fi off (menu bar). Close Numbers and Notes. Muselet running, Calendar can stay closed.
4. After the demo: `setup_mac.sh teardown --apply` removes only what setup created.

## Spoken lines

| t | Who | Line / bubble (<= 12 words) |
|---|---|---|
| 0:00 | Advisor (holds Right Option) | "Prep me for my meeting with the Hendersons." |
| 0:03 | Mascot | "Henderson review Monday ten. Pulling their file." |
| 0:30 | Mascot | "5 opportunities found. Brief is in Notes." (count only; the amounts are different kinds and are never summed) |
| 0:35 | Advisor (presenter aside) | "Wi-Fi is off. Nothing left this Mac." |
| 0:40 | Mascot (on follow-up "what's blocked?") | "VXUS harvest is wash-sale blocked until November eleventh." |

## Expected agent steps (apps in order)

| t | App | Step | Verification (`expect` / check) |
|---|---|---|---|
| 0:02 | Calendar | Find next event matching "Henderson": `Henderson annual review`, 2026-10-26 10:00-11:00 | event found; start date parsed by code |
| 0:05 | Finder | `open "~/Documents/Clients/Henderson"`; list files | `title~"Henderson"` |
| 0:08 | (brain) | Read `last_meeting_notes.txt`, `profile.json`, `targets.json`, `activity_last_60d.csv` | files parsed, no load warnings |
| 0:10 | Numbers | `open` `portfolio.xlsx` (Holdings sheet is what the advisor sees) | `numbers_wait_script(path)`: the open document whose file is that path |
| 0:12 | (brain) | `prep(load_household(dir))`: allocation, rebalance, TLH + wash sale, cash, Roth room, donation | all values carry evidence |
| 0:15 | Numbers | `script applescript` = `numbers_highlight_script(prep, path=xlsx)` (one call) | BND row 13 + VNQ row 5 green, VXUS row 11 amber |
| 0:19 | Numbers | `script applescript` = `numbers_review_script(prep, path=xlsx)` (one call) | sheet `Muselet Review` with tables `Muselet Allocation` and `Muselet Trades` (a user's sheet of that name is never deleted; ours gets replaced, a foreign one makes us write `Muselet Review 2`) |
| 0:24 | Notes | `script applescript` = `notes_brief_script(prep, phrasing)` (one call) | note "Henderson — annual review prep (Muselet)" in folder Clients, updated in place if it exists; nothing deleted |
| 0:28 | Notes | `open "Notes"`, show the note | `appears "Henderson — annual review prep (Muselet)"` |
| 0:30 | (mascot) | `done` + bubble | harness checks below |

Generate the three scripts offline for inspection:
`PYTHONPATH=ml/src python3 -m brain.advisor script numbers-highlight|numbers-review|notes-brief --household ~/Documents/Clients/Henderson`.
The highlight script also selects the Holdings sheet; nothing is saved to the xlsx.

## Success checks (run after the take)

Numbers (cells highlighted, Review sheet):
```
osascript -e 'tell application id "com.apple.Numbers" to tell sheet "Holdings" of front document to tell table 1 to return {background color of cell 1 of row 13, background color of cell 1 of row 5, background color of cell 1 of row 11}'
# expect {{50886, 61423, 52942}, {50886, 61423, 52942}, {65535, 58853, 39321}}  (green BND, green VNQ, amber VXUS)
osascript -e 'tell application id "com.apple.Numbers" to tell front document to return {name of every sheet, name of every table of sheet "Muselet Review"}'
# expect {"Holdings", "Muselet Review"}, {"Muselet Allocation", "Muselet Trades"}
```

Notes (note exists with the right numbers):
```
osascript -e 'tell application id "com.apple.Notes" to return plaintext of (first note of folder "Clients" whose name is "Henderson — annual review prep (Muselet)")' \
  | grep -c -e '\$1,739,656.00' -e '\$118,151.60' -e '\$68,480.00' -e '\$61,400.00' -e '\$53,472.00' -e '\$30,825.00' -e '2026-11-11'
# expect 7
```
The note must also show: equity 67.87% vs 60% target (out of band), bonds 27.14% vs 35%, "VXUS ... wash-sale
blocked", replacement pairs BND→AGG and VNQ→SCHH, "lake house down payment $120,000.00" reserve, AAPL and MSFT donation lots.

Offline proof: Wi-Fi icon off in the menu bar during the whole take; the `utterance.ctx.online` field in
`runs/traces/` is `false` for the take.

## Numbers the presenter can quote

Household $1,739,656.00 (invested $1,503,176.00). Allocation 67.87 / 27.14 / 4.99 vs 60 / 35 / 5. Rebalance in
Mark's IRA: sell $112,785.60 VTI + $5,524.80 VXUS, buy $118,151.60 AGG, $0 gains realized. Idle savings
$68,480.00. Roth conversion room $61,400.00 (2026 MFJ 22% bracket tops out at $211,400, IRS Rev. Proc.
2025-32). Harvestable losses $30,825.00 (BND, VNQ); VXUS blocked by the IRA buy 12 days ago. Gifting AAPL +
MSFT lots to a DAF avoids $53,472.00 of gains.
