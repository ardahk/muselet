# Second statements: regenerate with other seeds; check outliers/duplicates; remove planted outlier; plant others.
import sys, io, contextlib, pathlib, tempfile, shutil, json
sys.path.insert(0, 'ml/src')
from decimal import Decimal as D
from brain.finance.statement import load_statement, Txn
from brain.finance.detect import find_outliers, find_duplicates
src = pathlib.Path('evals/fixtures/finance/generate.py').read_text()
def rebalance(txns):
    out=[];bal=txns[0].balance-txns[0].amount
    for i,t in enumerate(txns,1):
        bal+=t.amount; out.append(Txn(i,t.date,t.description,t.amount,bal))
    return out
res={'seeds':0,'fp_with':0,'fp_without':0,'miss_400':0,'miss_250groc':0,'dups_ok':0}
for seed in range(1,41):
    d=pathlib.Path(tempfile.mkdtemp())
    s=src.replace('random.Random(1337)',f'random.Random({seed})').replace('OUT = Path(__file__).resolve().parent',f'OUT = Path("{d}")').replace('    check_spec(rows, truth, budget_truth, receipts_truth)\n','')
    g={'__name__':'gen'}
    try:
        with contextlib.redirect_stdout(io.StringIO()): exec(compile(s,'gen','exec'),g); g['main']()
    except Exception as e:
        shutil.rmtree(d); continue
    txns=load_statement((d/'bank_statement_oct2026.csv').read_text()); shutil.rmtree(d)
    res['seeds']+=1
    apple=[t.row for t in txns if t.amount==D('-1299.00')]
    o=find_outliers(txns)
    if o!=apple: res['fp_with']+=1; print('seed',seed,'outliers',o,[ (txns[r-1].description,txns[r-1].amount) for r in o])
    no=rebalance([t for t in txns if t.amount!=D('-1299.00')])
    o2=find_outliers(no)
    if o2: res['fp_without']+=1; print('seed',seed,'no-outlier stmt flags',[(no[r-1].description,no[r-1].amount) for r in o2])
    p=rebalance(no[:60]+[Txn(0,no[60].date,'TARGET',D('-400.00'),D(0))]+no[60:])
    if not any(p[r-1].amount==D('-400.00') for r in find_outliers(p)): res['miss_400']+=1
    if len(find_duplicates(txns))==2: res['dups_ok']+=1
print(res)
