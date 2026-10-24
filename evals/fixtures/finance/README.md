# Finance demo + eval fixtures (October 2026)

Persona: **Alex Rivera**, student/freelancer in Berkeley. All files are produced by
`generate.py` (Python 3.12, stdlib + openpyxl + pillow, `random.Random(1337)`); truth files are
computed from the generated CSV, never by hand. Regenerate with:

```
python3 evals/fixtures/finance/generate.py
```

Output is byte-stable across runs on the same machine. Receipt PNG pixels depend on the monospace font
found (DejaVu Sans Mono on Linux, Menlo on macOS); the committed PNGs were rendered with DejaVu Sans Mono.
The text content and all truth files do not depend on the font.

## Files

| File | What it is |
|---|---|
| `bank_statement_oct2026.csv` | 120-row checking statement, `Date,Description,Amount,Balance`; opening balance 3,120.55; debits negative; running balance; sorted by date. |
| `bank_statement_oct2026.truth.json` | Per-row category, duplicate pairs, `duplicate_status` (`open`, or `refunded` with the `refund_row` that reversed it), outlier row, refund row, `weekend_charges` (debits on Sat/Sun), `category_spend` (debits minus refunds), `total_income`, `total_spend`, `net`, `closing_balance`. Rows are 1-based (excluding header). |
| `budget_oct2026.xlsx` | Sheet `Budget`: `Category | Budget | Actual | Remaining` for Rent, Groceries, Dining, Transport, Shopping, Subscriptions, Utilities, Health. Actual and Remaining are empty (the agent fills them). |
| `budget_oct2026.truth.json` | Expected `actual` (= category_spend), `remaining` (= Budget - Actual) and `over_budget`. |
| `receipts/receipt_01..08.png` | 600x900 receipts. 1-6 match a statement row (same total): receipts 2 and 4 print the store name (`Trader Joe's #127`, `Berkeley Bowl #2`) instead of the bank descriptor, so matching must be fuzzy, and receipt 5 is dated the day before the charge posts (`posting_delay_days: 1`). 7 matches merchant+date but its TOTAL has two digits transposed; 8 (`PHILZ COFFEE`, between Peet's and Blue Bottle charges) matches nothing. Every line item is at least 20% of the subtotal; groceries carry no sales tax (California exempts them), everything else 10.25%. |
| `receipts.truth.json` | `{receipt: {match_row, status: matched|amount_mismatch|no_match, total, merchant, date}}` (`merchant`/`date` as printed on the receipt); the delayed receipt has `posting_delay_days`, the amount_mismatch entry has `statement_amount` and `transposed_digits: true`. |
| `setup_mac.sh` | Stages the demo on the Mac: copies the statement, budget and receipts into `~/Documents/Finance/` (`Receipts/`), opens nothing. `--dry-run` (default) / `--apply`; `teardown` removes only what it created; `reset` closes the demo documents without saving and restores the files. |

Planted anomalies: duplicate `UBER TRIP -23.47` on 10-09, duplicate `AMAZON MKTP -64.99` on 10-21,
outlier `APPLE STORE -1299.00` on Sat 10-24, refund `AMAZON MKTP REFUND +64.99` on 10-28 (Shopping,
counts as negative spend). No other exact (date, description, amount) duplicates exist. The Amazon
duplicate was already refunded on 10-28 (`duplicate_status: refunded`), so only the Uber pair is an open
dispute. `VENMO FROM SAM` (+45.00) is Income in the truth, but no general rule can know a P2P credit is
income, so the engine asks (with `BERKELEY BOWL`, an unknown grocer) instead of assuming.

## Demo / eval tasks

1. **Categorize the statement into the budget**: fill `Actual` (and `Remaining`) in `budget_oct2026.xlsx`
   (or the Numbers/Google Sheets import) from the CSV. Check against `budget_oct2026.truth.json`.
2. **Find duplicate charges**: report the two duplicate pairs (`duplicates` in the statement truth).
3. **Flag the outlier**: the $1,299.00 Apple Store purchase (`outliers`).
4. **Reconcile receipts**: match each receipt to a statement row; flag receipt 7 (amount mismatch)
   and receipt 8 (no matching transaction). Check against `receipts.truth.json`.
5. **Compute over-budget categories**: list categories with Remaining < 0 (`over_budget`).

## Story numbers (asserted by `generate.py`; generation fails if any drifts)

| | |
|---|---|
| Opening balance | 3,120.55 |
| Total income | 4,845.00 (2 x payroll 2,400.00 + Venmo 45.00) |
| Total spend (debits minus refunds) | 4,112.26 |
| Net | +732.74 |
| Closing balance | 3,853.29 |

| Category | Budget | Actual | Remaining |
|---|---:|---:|---:|
| Rent | 1,650 | 1,625.00 | 25.00 |
| Groceries | 400 | 298.70 | 101.30 |
| Dining | 250 | 347.21 | -97.21 |
| Transport | 150 | 121.06 | 28.94 |
| Shopping | 200 | 1,480.34 | -1,280.34 |
| Subscriptions | 60 | 42.97 | 17.03 |
| Utilities | 180 | 149.07 | 30.93 |
| Health | 80 | 47.91 | 32.09 |

`over_budget` is exactly **Dining** and **Shopping**. Shopping is over almost entirely because of the
$1,299.00 Apple Store outlier (without it Shopping would be 181.34, under budget); Dining is over by
$97.21 (lots of coffee). Every other category is under budget with at least $15 remaining. The asserted
rules: income 4,845.00, spend 3,900-4,300, net > 0, Dining over by 40-120, Shopping minus the outlier
<= budget, remaining >= 15 elsewhere, the planted anomalies above, and the receipt statuses.
