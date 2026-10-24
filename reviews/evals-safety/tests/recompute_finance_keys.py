import csv, json, datetime as dt
from collections import defaultdict, Counter
rows=list(csv.DictReader(open('bank_statement_oct2026.csv')))
print('nrows',len(rows))
cat={'PAYROLL ACME LABS':'Income','VENMO FROM SAM':'Income','RENT OAKLAND PROPERTIES':'Rent','PG&E':'Utilities','COMCAST XFINITY':'Utilities',
'SPOTIFY':'Subscriptions','NETFLIX':'Subscriptions','APPLE ICLOUD':'Subscriptions','OPENAI CHATGPT':'Subscriptions',
"TRADER JOE'S":'Groceries','SAFEWAY':'Groceries','BERKELEY BOWL':'Groceries','CHIPOTLE':'Dining','SWEETGREEN':'Dining','BLUE BOTTLE COFFEE':'Dining','DOORDASH':'Dining',
'BART CLIPPER':'Transport','UBER TRIP':'Transport','LYFT RIDE':'Transport','CHEVRON':'Transport','AMAZON MKTP':'Shopping','TARGET':'Shopping','APPLE STORE':'Shopping','AMAZON MKTP REFUND':'Shopping',
'CVS PHARMACY':'Health','KAISER COPAY':'Health'}
bal=3120.55; spend=defaultdict(float); inc=0; issues=[]
prev=None
descs=Counter()
for i,r in enumerate(rows,1):
    a=float(r['Amount']); bal=round(bal+a,2)
    if abs(bal-float(r['Balance']))>0.005: issues.append(('balance',i,bal,r['Balance']))
    if r['Date']<(prev or ''): issues.append(('order',i))
    prev=r['Date']
    if r['Description'] not in cat: issues.append(('unknown desc',i,r['Description']))
    c=cat.get(r['Description'],'?'); descs[r['Description']]+=1
    if c=='Income': inc+=a
    else: spend[c]+= -a
    if len(r['Amount'].split('.')[-1])!=2: issues.append(('dp',i))
print('issues',issues)
print('desc counts',dict(descs))
spend={k:round(v,2) for k,v in spend.items()}
print('spend',spend,'total',round(sum(spend.values()),2),'income',round(inc,2),'net',round(inc-sum(spend.values()),2),'closing',bal)
key=Counter((r['Date'],r['Description'],r['Amount']) for r in rows)
print('dups',[(k,[i for i,r in enumerate(rows,1) if (r['Date'],r['Description'],r['Amount'])==k]) for k,v in key.items() if v>1])
wk=[i for i,r in enumerate(rows,1) if dt.date.fromisoformat(r['Date']).weekday()>=5]
wkd=[i for i in wk if float(rows[i-1]['Amount'])<0]
print('weekend all',wk); print('weekend debits',wkd)
print('2026-10-24 weekday',dt.date(2026,10,24).strftime('%A'))
amts=sorted(((float(r['Amount']),i,r['Description']) for i,r in enumerate(rows,1)))
print('largest debits',amts[:4]); print('refunds',[(i,r) for i,r in enumerate(rows,1) if 'REFUND' in r['Description']])
# ranges
rng={'Groceries':(12,95),'Dining':(4.5,42),'Transport':(2.5,58),'Shopping':(8,120),'Health':(10,45)}
for i,r in enumerate(rows,1):
    c=cat.get(r['Description']);a=-float(r['Amount'])
    if c in rng and r['Description']!='AMAZON MKTP REFUND' and not (rng[c][0]<=a<=rng[c][1]): print('out of range',i,r)
t=json.load(open('bank_statement_oct2026.truth.json'))
mism=[(x['row'],x['category'],cat.get(rows[x['row']-1]['Description'])) for x in t['rows'] if x['category']!=cat.get(rows[x['row']-1]['Description'])]
print('category mismatches',mism)
for k in ['category_spend','total_income','total_spend','net','closing_balance']: print(k,t[k])
b=json.load(open('budget_oct2026.truth.json'))
rem={k:round(b['budget'][k]-spend[k],2) for k in b['budget']}
print('remaining',rem,'over',[k for k,v in rem.items() if v<0])
# receipts vs rows
rt=json.load(open('receipts.truth.json'))
for f,v in rt.items():
    mr=v['match_row']
    if mr: r=rows[mr-1]; print(f,v['status'],v['merchant'],v['date'],v['total'],'| row',mr,r['Date'],r['Description'],r['Amount'])
    else:
        cands=[(i,r) for i,r in enumerate(rows,1) if abs(abs(float(r['Amount']))-v['total'])<0.005]
        print(f,'no_match; rows with same amount:',cands)
