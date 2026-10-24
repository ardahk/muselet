"""Independent recompute of advisor truth.json from the henderson files (own code, Decimal)."""
import csv, json, sys, re, datetime as dt
from decimal import Decimal as D, ROUND_HALF_UP
H = sys.argv[1]
C = lambda x: x.quantize(D('0.01'), rounding=ROUND_HALF_UP)
rows = list(csv.DictReader(open(f'{H}/portfolio.csv')))
act = list(csv.DictReader(open(f'{H}/activity_last_60d.csv')))
prof = json.load(open(f'{H}/profile.json')); tg = json.load(open(f'{H}/targets.json'))
T = json.load(open(f'{H}/truth.json')); asof = dt.date.fromisoformat(prof['as_of'])
bad = []
def chk(name, mine, theirs):
    if str(mine) != str(theirs): bad.append((name, str(mine), str(theirs)))
for i, r in enumerate(rows, 1):
    mv = C(D(r['Shares']) * D(r['Price'])); chk(f'mv{i}', mv, C(D(r['Market value'])))
    chk(f'gl{i}', C(mv - D(r['Cost basis'])), C(D(r['Unrealized G/L'])))
kind = lambda a: 'sav' if a == 'Savings' else 'roth' if 'Roth' in a else 'trad' if 'IRA' in a else 'tax'
inv = [r for r in rows if kind(r['Account']) != 'sav']
tot = sum(D(r['Market value']) for r in inv); chk('invested', C(tot), T['totals']['invested'])
chk('household', C(sum(D(r['Market value']) for r in rows)), T['totals']['household'])
val = {k: sum(D(r['Market value']) for r in inv if r['Asset class'] == k) for k in tg['targets_pct']}
for c in T['allocation']['classes']:
    k = c['asset_class']; cur = val[k] * 100 / tot
    chk('pct ' + k, C(cur), c['current_pct']); chk('drift ' + k, C(cur - D(tg['targets_pct'][k])), c['drift_pp'])
    chk('oob ' + k, abs(cur - D(tg['targets_pct'][k])) > 5, c['out_of_band'])
eq = (val['US equity'] + val['Intl equity']) * 100 / tot; chk('equity', C(eq), T['allocation']['groups'][0]['current_pct'])
# rebalance: deltas to target
for k in ('US equity', 'Intl equity', 'Bonds'):
    d = C(tot * D(tg['targets_pct'][k]) / 100 - val[k])
    tr = sum(D(t['amount']) * (1 if t['side'] == 'buy' else -1) for t in T['rebalance']['trades'] if t['asset_class'] == k)
    chk('delta ' + k, d, C(tr))
# each sell fits within the account's holding; buys funded by same-account cash + proceeds
for a in {t['account'] for t in T['rebalance']['trades']}:
    cash = sum(D(r['Market value']) for r in inv if r['Account'] == a and r['Asset class'] == 'Cash')
    flow = sum(D(t['amount']) * (1 if t['side'] == 'sell' else -1) for t in T['rebalance']['trades'] if t['account'] == a)
    if cash + flow < 0: bad.append(('unfunded', a, str(cash + flow)))
    for t in T['rebalance']['trades']:
        if t['account'] == a and t['side'] == 'sell':
            held = sum(D(r['Market value']) for r in inv if r['Account'] == a and r['Ticker'] == t['ticker'])
            if D(t['amount']) > held: bad.append(('oversell', t))
    if kind(a) == 'tax': bad.append(('taxable trade', a))
# TLH with wash sale window (30 days before as-of; any account), own lot purchase excluded
mine = []
for i, r in enumerate(rows, 1):
    if kind(r['Account']) != 'tax' or not r['Lot date'] or -D(r['Unrealized G/L']) < 1000: continue
    buys = [a for a in act if a['Action'] == 'Buy' and a['Ticker'] == r['Ticker']
            and 0 <= (asof - dt.date.fromisoformat(a['Date'])).days <= 30]
    mine.append((i, r['Ticker'], C(-D(r['Unrealized G/L'])), 'wash_sale_blocked' if buys else 'ok',
                 (max(dt.date.fromisoformat(a['Date']) for a in buys) + dt.timedelta(31)).isoformat() if buys else None))
theirs = [(e['lot']['row'], e['lot']['ticker'], e['loss'], e['status'], e.get('earliest_clean_sale')) for e in T['tlh']['lots']]
chk('tlh', sorted((a, b, str(c), d, e) for a, b, c, d, e in mine), sorted(theirs))
chk('harvest', C(sum(m[2] for m in mine if m[3] == 'ok')), T['tlh']['harvestable_loss_total'])
# cash
sav = sum(D(r['Market value']) for r in rows if kind(r['Account']) == 'sav')
lake = D(re.search(r'\$([\d,]+)', open(f'{H}/last_meeting_notes.txt').read().split('Lake house')[1]).group(1).replace(',', ''))
chk('cash', C(sav - 6 * D(prof['monthly_expenses']) - lake), T['cash']['excess'])
# Roth: IRS Rev. Proc. 2025-32 MFJ 22% top, from my own extraction (reviews/finance/tests/irs_2026_reference.json)
chk('roth', C(D('211400') - D(prof['estimated_taxable_income'])), T['roth']['room'])
# donation: long-term = sold after the 1-year anniversary (holding period starts day after trade date)
def lt(d):
    d = dt.date.fromisoformat(d); return asof > d.replace(year=d.year + 1)
pool = sorted(((D(r['Unrealized G/L']) / D(r['Cost basis']), i, r) for i, r in enumerate(rows, 1)
               if kind(r['Account']) == 'tax' and r['Lot date'] and D(r['Unrealized G/L']) > 0 and lt(r['Lot date'])), key=lambda x: (-x[0], x[1]))[:2]
chk('don rows', [p[1] for p in pool], [c['lot']['row'] for c in T['donation']['candidates']])
chk('don pct', [str(C(p[0] * 100)) for p in pool], [c['gain_pct'] for c in T['donation']['candidates']])
chk('don gain', C(sum(D(p[2]['Unrealized G/L']) for p in pool)), T['donation']['gain_avoided_total'])
print('invested', tot, {k: str(C(v * 100 / tot)) for k, v in val.items()}, 'equity', C(eq))
print('ADVISOR TRUTH RECONCILES' if not bad else 'MISMATCH', bad)
