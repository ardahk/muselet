# Advisor mode fixtures: the Henderson household

Demo + eval data for "prep me for my meeting with the Hendersons" (on-device, Wi-Fi off). Everything in
`henderson/` is written by `generate.py` (Python 3.12, stdlib + openpyxl); `truth.json` is recomputed from
the written files by independent code in `generate.py`, and the planted facts below are asserted there.
`ml/tests/test_advisor.py` checks that `brain.advisor` reproduces `truth.json` to the cent.

```
python3 evals/fixtures/advisor/generate.py                       # regenerate (byte-stable)
PYTHONPATH=ml/src python3 -m brain.advisor prep --household evals/fixtures/advisor/henderson
PYTHONPATH=ml/src python3 -m pytest ml/tests/test_advisor.py
```

Prices are fictional and fixed as of 2026-10-23. Money in `truth.json` is 2-decimal strings.

## Household

Mark (62) and Elena (60) Henderson, married filing jointly, California. Household $1,739,656.00:
Joint taxable brokerage $859,182.00, Mark Traditional IRA $589,535.00, Elena Roth IRA $54,459.00,
Savings $236,480.00. 22 lots / 15 positions; VTI, MSFT, VXUS and BND have multiple taxable lots.

| File | Contents |
|---|---|
| `portfolio.xlsx` / `portfolio.csv` | Sheet `Holdings`: Account, Ticker, Name, Asset class, Lot date, Shares, Cost basis (lot total), Price, Market value, Unrealized G/L. One row per lot. Sheet row = CSV data row + 1. |
| `targets.json` | 40% US equity, 20% Intl equity (60% equity), 35% Bonds, 5% Cash; band ±5 pp per class. |
| `activity_last_60d.csv` | Buys/sells 2026-08-24..10-23 across all accounts. |
| `profile.json` | MFJ, CA, ages, 2026 taxable income before conversion $150,000, monthly expenses $8,000, goals. |
| `last_meeting_notes.txt` | 2026-07-23 notes: $120,000 lake-house down payment next spring, charitable giving interest. |
| `annual_review.ics` | "Henderson annual review", 2026-10-26 10:00-11:00 (floating local time). |
| `truth.json` | Expected `brain.advisor.prep()` output without `evidence`. |

## Rules (as implemented in `ml/src/brain/advisor/core.py`)

- **Allocation** covers the investment accounts (taxable + IRAs, $1,503,176.00). Savings is the liquidity
  bucket and is handled by the cash rule.
- **Rebalance**: if any class is more than 5 pp from target, every non-cash class is traded back to
  target (cash lands on target as the residual). Trades go to tax-advantaged accounts first
  (Traditional IRA, then Roth IRA, taxable last; taxable sells would use highest-cost lots first), so no
  gains are realized. A buy is funded by the same account's sweep cash plus sale proceeds. A buy never
  uses a ticker that has a TLH lot (that would wash the harvested loss); it uses the pair instead.
- **TLH**: taxable lots with unrealized loss >= $1,000. Wash-sale blocked if the same ticker was bought in
  any account (IRAs included, per IRS Pub. 550) in the 30 days before the as-of date; earliest clean sale =
  last such buy + 31 days. Pairs: VTI→ITOT, VXUS→IXUS, BND→AGG, VNQ→SCHH, VOO→IVV, VEA→IEFA, VWO→IEMG,
  BNDX→IAGG.
- **Cash excess** = savings − 6 × monthly expenses − lake-house reserve (the $ amount in the notes sentence
  mentioning the lake house down payment; kept liquid because it is needed within a year).
- **Roth room** = top of the 2026 MFJ 22% bracket − estimated taxable income, floor 0.
- **Donation candidates**: taxable lots with a gain held more than 1 year (holding period starts the day
  after the trade date, IRS Pub. 550), top 2 by gain %.
- **Opportunities** are ranked by `impact_usd`: dollars to move (rebalance), idle savings (cash), convertible
  amount (Roth), harvestable losses (TLH), gains avoided (donation).

## Truth values

- Allocation (current vs target, drift): US equity 47.50% vs 40 (+7.50, out of band); Intl 20.37% vs 20
  (+0.37); Bonds 27.14% vs 35 (−7.86, out of band); Cash 4.99% vs 5 (−0.01); Equity total 67.87% vs 60 (+7.87).
- Rebalance (Mark Traditional IRA): sell $112,785.60 VTI, sell $5,524.80 VXUS, buy $118,151.60 AGG (instead
  of BND). Realized gain $0.00; post-trade 40.00/20.00/35.00/5.00.
- TLH: BND 2021-08-02 loss $21,825.00 ok → AGG; VNQ 2022-01-03 loss $9,000.00 ok → SCHH; VXUS 2026-02-09 loss
  $3,640.00 wash_sale_blocked (VXUS bought in Mark Traditional IRA 2026-10-11, 12 days earlier) → IXUS, clean
  from 2026-11-11. Harvestable total $30,825.00.
- Cash excess: $236,480.00 − $48,000.00 − $120,000.00 = $68,480.00.
- Roth room: $211,400.00 − $150,000.00 = $61,400.00.
- Donation candidates: AAPL 2012-09-17 (+925.61%, gain $27,324.00), MSFT 2015-11-02 (+810.04%, gain
  $26,148.00); $59,652.00 market value, $53,472.00 gain avoided.

Distractors: VTI 2026-03-02 taxable lot loses $628 (below threshold); VTI was bought in the IRA 23 days ago
(irrelevant: no VTI TLH lot); VNQ was bought in the Roth 51 days ago (outside the window, so VNQ harvest
is ok); PLTR 2025-10-23 (+901.65%) is held exactly one year, so short-term and not a donation candidate.

## Sources (fetched 2026-10-24)

- IRS Rev. Proc. 2025-32, section 4.01, Table 1 (Married Individuals Filing Joint Returns), page 10:
  https://www.irs.gov/pub/irs-drop/rp-25-32.pdf. Tax year 2026 MFJ brackets: 10% to $24,800; 12% to
  $100,800; 22% to $211,400; 24% to $403,550; 32% to $512,450; 35% to $768,700; 37% above. Same figures in
  IRS news release IR-2025-103 (Oct. 9, 2025): https://www.irs.gov/newsroom/irs-releases-tax-inflation-adjustments-for-tax-year-2026-including-amendments-from-the-one-big-beautiful-bill
  (it also lists the 2026 MFJ standard deduction, $32,200; not used because the profile gives taxable income).
  Code constants: `ml/src/brain/advisor/tax.py`.
- IRS Publication 550, "Wash Sales" (30 days before or after; acquisitions for your IRA or Roth IRA count)
  and "Holding Period" (begins the day after the trade date): https://www.irs.gov/publications/p550
- IRMAA is not modelled or mentioned (not verified). State (CA) tax is not modelled.

## Mac demo

`setup_mac.sh` stages the household on the demo Mac; `DEMO.md` is the 45-second script.
