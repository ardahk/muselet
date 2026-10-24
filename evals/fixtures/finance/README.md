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
| `bank_statement_oct2026.truth.json` | Per-row category, duplicate pairs, outlier row, refund row, `category_spend` (debits minus refunds), `total_income`, `total_spend`, `net`, `closing_balance`. Rows are 1-based (excluding header). |
| `budget_oct2026.xlsx` | Sheet `Budget`: `Category | Budget | Actual | Remaining` for Rent, Groceries, Dining, Transport, Shopping, Subscriptions, Utilities, Health. Actual and Remaining are empty (the agent fills them). |
| `budget_oct2026.truth.json` | Expected `actual` (= category_spend), `remaining` (= Budget - Actual) and `over_budget`. |
| `receipts/receipt_01..08.png` | 600x900 receipts. 1-6 match a statement row exactly (merchant, date, total); 7 matches merchant+date but its TOTAL has two digits transposed; 8 (`PHILZ COFFEE`) matches nothing. |
| `receipts.truth.json` | `{receipt: {match_row, status: matched|amount_mismatch|no_match, total, merchant, date}}`. |

Planted anomalies: duplicate `UBER TRIP -23.47` on 10-09, duplicate `AMAZON MKTP -64.99` on 10-21,
outlier `APPLE STORE -1299.00` on Sat 10-24, refund `AMAZON MKTP REFUND +64.99` on 10-28 (Shopping,
counts as negative spend). No other exact (date, description, amount) duplicates exist.

## Demo / eval tasks

1. **Categorize the statement into the budget**: fill `Actual` (and `Remaining`) in `budget_oct2026.xlsx`
   (or the Numbers/Google Sheets import) from the CSV. Check against `budget_oct2026.truth.json`.
2. **Find duplicate charges**: report the two duplicate pairs (`duplicates` in the statement truth).
3. **Flag the outlier**: the $1,299.00 Apple Store purchase (`outliers`).
4. **Reconcile receipts**: match each receipt to a statement row; flag receipt 7 (amount mismatch)
   and receipt 8 (no matching transaction). Check against `receipts.truth.json`.
5. **Compute over-budget categories**: list categories with Remaining < 0 (`over_budget`).

Note: with 120 rows of sampled spending, most variable categories exceed their budgets (by design of the
sampling spec), so `over_budget` contains Groceries, Dining, Transport, Shopping and Health.
