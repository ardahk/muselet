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
import re as _re
def _key(x): return _re.sub(r'[^A-Z]', '', _re.split(r'[\s#]', x.upper().replace("'", ''))[0])
for k, v in R.items():  # own rule: first word of the printed store name, charge posted 0-3 days later
    d0 = date.fromisoformat(v['date'])
    m = [i for i, r in enumerate(rows, 1) if _key(v['merchant']) == _key(r['Description'])
         and 0 <= (date.fromisoformat(r['Date']) - d0).days <= 3 and D(r['Amount']) < 0]
    ex = [i for i in m if -D(rows[i-1]['Amount']) == D(str(v['total']))]
    st = 'matched' if ex else ('amount_mismatch' if m else 'no_match')
    mr = (ex or m or [None])[0]
    if (st, mr) != (v['status'], v['match_row']): errs.append(f'receipt {k} {st} {mr} {m}')
if 'weekend_charges' in T:
    wk = [i for i, r in enumerate(rows, 1) if D(r['Amount']) < 0 and date.fromisoformat(r['Date']).weekday() >= 5]
    if wk != T['weekend_charges']: errs.append('weekend')
if 'duplicate_status' in T:
    for dd in T['duplicate_status']:
        a = rows[dd['rows'][0]-1]
        rf = [i for i, r in enumerate(rows, 1) if D(r['Amount']) == -D(a['Amount']) and 'REFUND' in r['Description']
              and r['Description'].startswith(a['Description']) and r['Date'] >= a['Date']]
        if (dd['status'], dd['refund_row']) != (('refunded', rf[0]) if rf else ('open', None)): errs.append('dup_status')
print('income', inc, 'spend', tot, 'net', inc - tot, 'closing', bal, 'over', over)
print({c: str(B['budget'][c] - spend.get(c, D(0))) for c in B['categories']})
print('weekday of rows', T['outliers'], [date.fromisoformat(rows[i-1]['Date']).strftime('%a') for i in T['outliers']])
print('ERRORS' if errs else 'ALL TRUTH RECONCILES', errs)
