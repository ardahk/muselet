"""Independent recompute of finance truth files from the CSV (Decimal only)."""
import csv, json, sys
from decimal import Decimal as D
from datetime import date
from pathlib import Path
F = Path(sys.argv[1])
rows = list(csv.DictReader(open(F/'bank_statement_oct2026.csv')))
T = json.load(open(F/'bank_statement_oct2026.truth.json'))
B = json.load(open(F/'budget_oct2026.truth.json'))
R = json.load(open(F/'receipts.truth.json'))
errs = []
bal = D(str(T['opening_balance']))
for i, r in enumerate(rows, 1):
    bal += D(r['Amount'])
    if bal != D(r['Balance']): errs.append(f'balance row {i}')
if bal != D(str(T['closing_balance'])): errs.append('closing')
cat = {x['row']: x['category'] for x in T['rows']}
spend, inc = {}, D(0)
for i, r in enumerate(rows, 1):
    a = D(r['Amount'])
    if cat[i] == 'Income': inc += a
    else: spend[cat[i]] = spend.get(cat[i], D(0)) - a
tot = sum(spend.values())
for k, v in (('total_income', inc), ('total_spend', tot), ('net', inc - tot)):
    if D(str(T[k])) != v: errs.append(k)
for c in B['categories']:
    v = spend.get(c, D(0))
    if D(str(T['category_spend'][c])) != v: errs.append('spend ' + c)
    if D(str(B['actual'][c])) != v: errs.append('actual ' + c)
    if D(str(B['remaining'][c])) != D(B['budget'][c]) - v: errs.append('remaining ' + c)
over = [c for c in B['categories'] if D(B['budget'][c]) - spend.get(c, D(0)) < 0]
if over != B['over_budget']: errs.append('over_budget')
g = {}
for i, r in enumerate(rows, 1): g.setdefault((r['Date'], r['Description'], r['Amount']), []).append(i)
if [v for v in g.values() if len(v) > 1] != T['duplicates']: errs.append('duplicates')
for k, v in R.items():
    m = [i for i, r in enumerate(rows, 1) if r['Description'] == v['merchant'] and r['Date'] == v['date']]
    ex = [i for i in m if -D(rows[i-1]['Amount']) == D(str(v['total']))]
    st = 'matched' if ex else ('amount_mismatch' if m else 'no_match')
    mr = (ex or m or [None])[0]
    if (st, mr) != (v['status'], v['match_row']) or len(m) > 1: errs.append(f'receipt {k} {st} {mr} {m}')
print('income', inc, 'spend', tot, 'net', inc - tot, 'closing', bal, 'over', over)
print({c: str(B['budget'][c] - spend.get(c, D(0))) for c in B['categories']})
print('weekday of rows', T['outliers'], [date.fromisoformat(rows[i-1]['Date']).strftime('%a') for i in T['outliers']])
print('ERRORS' if errs else 'ALL TRUTH RECONCILES', errs)
