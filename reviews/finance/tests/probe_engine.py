import json, sys, csv, io
from decimal import Decimal as D
from datetime import date, timedelta
sys.path.insert(0, 'ml/src')
from brain.finance.statement import load_statement, load_budget, Txn
from brain.finance.detect import find_outliers, find_duplicates, find_refunds, weekend_charges
from brain.finance.categorize import categorize, rule_category
from brain.finance.receipts import reconcile_receipts, merchant_match
from brain.finance.report import analyze
F = 'evals/fixtures/finance/'
txns = load_statement(open(F+'bank_statement_oct2026.csv').read())
T = json.load(open(F+'bank_statement_oct2026.truth.json'))
truth = {x['row']: x['category'] for x in T['rows']}
cats = categorize(txns, list(json.load(open(F+'budget_oct2026.truth.json'))['budget']))
acc = sum(cats[r][0] == truth[r] for r in truth) / len(truth)
print('rules-only accuracy', acc, 'wrong', [(r, txns[r-1].description, cats[r], truth[r]) for r in truth if cats[r][0] != truth[r]])
# Refund vs duplicate linkage in report
budget = load_budget(F+'budget_oct2026.truth.json')
rep = analyze(txns, budget)
print('dups', rep['duplicates'], 'refunds', rep['refunds'])
for f in rep['flags']:
    if f['kind'] in ('duplicate', 'refund', 'outlier'): print(' ', f['kind'], f['rows'], f['rule'], '|', f['say'])
# rule probes
for d in ["RENT THE RUNWAY", "KEY LIME CAFE", "TRANSFER FROM SAVINGS", "COSTCO WHSE #123", "SHELL SERVICE STATION",
          "APPLE.COM/BILL", "SQ *BLUE BOTTLE", "TST* PHILZ COFFEE", "UBER   *EATS", "UBER *TRIP", "LYFT   *RIDE SUN 3PM",
          "AMZN Mktp US*2K4", "WHOLEFDS MKT 10234", "CHEVRON 0091234", "PEET'S #1234", "STARBUCKS STORE 05812",
          "ZELLE TO MOM", "VENMO PAYMENT", "ATM WITHDRAWAL", "CHECK 1043", "IRS USATAXPYMT", "GOOGLE *YOUTUBE PREMIUM",
          "MATT'S BAR", "THE HOME DEPOT #0654", "PARKMOBILE", "SPOTHERO PARKING"]:
    print(f'  {d!r:32} -> {rule_category(d)}')
