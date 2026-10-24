You are a cloud executor for "muselet", a fully on-device macOS voice computer-use agent (repo
github.com/ardahk/muselet; work on branch `cloud/fixtures-docs`, open a PR to `main`). Read `AGENTS.md` first.
Hackathon deadline: Sun Oct 25 09:00 PDT — finish everything below by Sat Oct 24 10:00 PDT.
Secrets are env vars (HF_TOKEN, OPENAI_API_KEY, ANTHROPIC_API_KEY, TINKER_API_KEY): never print, log or commit them.
Do not use Tinker in this session. Three independent tasks; push each as soon as it is done.

## Task 1 — finance demo + eval fixtures (deterministic; this is an answer key, follow exactly)
Write `evals/fixtures/finance/generate.py` (Python 3.12, stdlib + openpyxl + pillow only, `random.Random(1337)`)
that produces every file below, and commit both the script and its outputs (all files are small).

Persona: Alex Rivera, student/freelancer in Berkeley. Month: October 2026.

1. `bank_statement_oct2026.csv` — columns `Date,Description,Amount,Balance` (Date `YYYY-MM-DD`; Amount negative =
   debit, positive = credit, 2 decimals; Balance running, opening balance 3,120.55 before the first row; rows sorted
   by date, stable within a date). Exactly 120 rows. Categories and merchants (Description strings exactly):
   - Income: `PAYROLL ACME LABS` +2400.00 on 10-01 and 10-15; `VENMO FROM SAM` +45.00 (one row, random date).
   - Rent: `RENT OAKLAND PROPERTIES` -1650.00 on 10-01.
   - Utilities: `PG&E` (one row, -60..-110), `COMCAST XFINITY` (one row, -79.99).
   - Subscriptions: `SPOTIFY` -11.99, `NETFLIX` -15.49, `APPLE ICLOUD` -2.99, `OPENAI CHATGPT` -20.00 (one row each).
   - Groceries: `TRADER JOE'S`, `SAFEWAY`, `BERKELEY BOWL` (-12..-95).
   - Dining: `CHIPOTLE`, `SWEETGREEN`, `BLUE BOTTLE COFFEE`, `DOORDASH` (-4.50..-42).
   - Transport: `BART CLIPPER`, `UBER TRIP`, `LYFT RIDE`, `CHEVRON` (-2.50..-58).
   - Shopping: `AMAZON MKTP`, `TARGET`, `APPLE STORE` (-8..-120, except the planted outlier).
   - Health: `CVS PHARMACY`, `KAISER COPAY` (-10..-45).
   Fill the remaining rows by sampling Groceries/Dining/Transport/Shopping/Health with weights 25/35/25/10/5,
   uniform random dates and amounts in the ranges above (2 decimals).
   Planted anomalies (must be present exactly):
   - Duplicate A: two identical rows `UBER TRIP` -23.47 on 10-09.
   - Duplicate B: two identical rows `AMAZON MKTP` -64.99 on 10-21.
   - Outlier: `APPLE STORE` -1299.00 on 10-24 (a Saturday).
   - Refund: `AMAZON MKTP REFUND` +64.99 on 10-28 (category Shopping, counts as negative spend).
   No other exact duplicates (same date+description+amount) may occur; regenerate random rows until true.
2. `bank_statement_oct2026.truth.json` — `{"rows":[{"row":1-based index,"category":...}], "duplicates":[[i,j],...],
   "outliers":[row], "refunds":[row], "category_spend": {category: positive total of debits minus refunds, 2 dp},
   "total_income", "total_spend", "net", "closing_balance"}`. Compute from the CSV, never by hand.
3. `budget_oct2026.xlsx` — one sheet `Budget`, header row `Category | Budget | Actual | Remaining`, rows in this order
   with budgets: Rent 1650, Groceries 400, Dining 250, Transport 150, Shopping 200, Subscriptions 60,
   Utilities 180, Health 80. Actual and Remaining cells empty. Plus `budget_oct2026.truth.json` with the expected
   Actual (= category_spend), Remaining (= Budget - Actual) and `over_budget` (categories with Remaining < 0).
4. `receipts/` — 8 PNG receipts (600x900, white background, monospace text rendered with pillow: merchant name,
   address line, date, 2-4 line items, subtotal, tax, TOTAL). Receipts 1-6 match a statement row exactly (merchant,
   date, total = |Amount|); receipt 7 matches a row's merchant and date but its TOTAL has two digits transposed
   (e.g. 18.40 vs 18.04); receipt 8 has no matching row at all (merchant `PHILZ COFFEE`). File names
   `receipt_01.png` .. `receipt_08.png`. Truth file `receipts.truth.json`: `{receipt: {"match_row": int|null,
   "status": "matched"|"amount_mismatch"|"no_match", "total": ...}}`.
5. `README.md` in that folder: what each file is and the 5 demo tasks it supports (categorize statement into budget;
   find duplicates; flag outlier; reconcile receipts; compute over-budget categories).

## Task 2 — offline docs corpus for local Q&A (ANSWER intent)
Build `docs_corpus.jsonl` with records `{"id","product","url","title","section","text"}` (text <= 350 words,
split on headings, keep keyboard shortcuts tables intact as text rows). Sources (respect robots.txt; polite rate
limiting): Adobe Premiere Pro user guide pages linked from https://helpx.adobe.com/premiere-pro/user-guide.html
(cap 400 pages) and the default keyboard shortcuts page; Apple Numbers for Mac user guide
https://support.apple.com/guide/numbers/welcome/mac (all topics); macOS keyboard shortcuts
https://support.apple.com/en-us/102650. These are copyrighted: do NOT commit the corpus to GitHub. Upload it as a
PRIVATE Hugging Face dataset `ardahk/muselet-docs` (HF_TOKEN; if the token lacks write permission, stop and
report). Commit only the scraper script (`tools/docs/scrape.py`) and stats (pages, chunks, tokens per product).

## Task 3 — Premiere Pro UXP bridge plugin (cannot be tested here; write it carefully from official docs)
Target: Adobe Premiere Pro 2026 (v26.x) on macOS. Using the official UXP Premiere Pro API docs
(https://developer.adobe.com/premiere-pro/uxp/) and samples (https://github.com/AdobeDocs/uxp-premiere-pro-samples),
write `premiere/muselet-bridge/` (manifest v5 + `index.js` [+ minimal html]) — a UXP panel plugin that connects OUT
to `ws://127.0.0.1:8766` (UXP plugins cannot host servers) and executes JSON commands
`{"id","cmd","args"}`, replying `{"id","ok","result"|"error"}`. Commands: `sequence_info` (active sequence name,
duration, playhead time, video/audio track and clip counts with clip names and start/end times), `add_marker`
(at playhead, optional name), `razor_at_playhead` (if the UXP API supports it; else return
`not_supported`), `add_transition` (default video transition between clip i and i+1 on track 1, if supported),
`move_playhead` (seconds), `export_sequence` (preset path, output path; use the encoder/export API if available),
`undo`. Use only APIs documented for the 2026 release; for each command note in comments the doc page used.
Also write `premiere/README.md`: exact steps to load the unsigned dev plugin on macOS (UXP Developer Tools / plugin
loading), required manifest permissions (network), and how to test with a tiny websocket echo server. Mark the
whole plugin UNTESTED in the README.

Report at the end of each task: files, stats, and anything you could not do.
