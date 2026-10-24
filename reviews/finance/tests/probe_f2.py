import sys, json, zipfile, re
sys.path.insert(0, 'ml/src')
from decimal import Decimal as D
from datetime import date
from brain.finance.statement import load_statement, load_budget, parse_money, Txn
from brain.finance.report import analyze
from brain.finance.receipts import reconcile_receipts, parse_receipt_text
from brain.finance import numbers_script as ns
F = 'evals/fixtures/finance/'
txns = load_statement(open(F + 'bank_statement_oct2026.csv').read())
budget = load_budget(F + 'budget_oct2026.xlsx')
rep = analyze(txns, budget)
b = rep['budget']
print('complete', rep['complete'], 'pending', b.get('pending'), 'needs_review', b.get('needs_review'))
print('actual', {k: str(v) for k, v in b['actual'].items()}, 'budget', {k: str(v) for k, v in budget.items()})
print('stmt', {k: str(v) for k, v in rep['statement'].items() if k != 'pending'})
z = zipfile.ZipFile(F + 'budget_oct2026.xlsx'); s = z.read('xl/worksheets/sheet1.xml').decode()
print('xlsx dimension', re.findall(r'<dimension ref="([^"]+)"', s), 'cols', re.findall(r'<col [^>]+>', s)[:6])
for m in ['($23.47)', '-$23.47', '\u221223.47', '1,299.00', '$1,299.00', '-23.47 ']:
    try: print(' parse_money', repr(m), parse_money(m))
    except Exception as e: print(' parse_money', repr(m), 'ERR', e)
tsv = 'Category\tBudget\tActual\tRemaining\nRent\t$1,625.00\t\t\nGroceries\t$500.00\t\t'
try: print('budget-as-statement', load_statement(tsv))
except Exception as e: print('budget-as-statement raises', type(e).__name__, e)
# receipt tolerance
T = [Txn(1, date(2026, 10, 5), 'SQ *BLUE BOTTLE', D('-12.00'), D('100')),
     Txn(2, date(2026, 10, 6), 'TST* NOPALITO', D('-57.60'), D('42.40')),
     Txn(3, date(2026, 10, 7), 'SHELL OIL 5741', D('-1.00'), D('41.40')),
     Txn(4, date(2026, 10, 9), 'SHELL OIL 5741', D('-48.20'), D('0'))]
R = [{'id': 'a', 'merchant': 'Blue Bottle Coffee', 'date': '2026-10-05', 'total': '5.00'},
     {'id': 'b', 'merchant': 'Nopalito', 'date': '2026-10-05', 'total': '48.00'},
     {'id': 'c', 'merchant': 'Shell', 'date': '2026-10-07', 'total': '48.20'}]
for k, v in reconcile_receipts(R, T).items(): print(' receipt', k, v)
for txt in ["CHIPOTLE\n2601 Telegraph\n10/19/2026\nBurrito 11.50\nSubtotal 14.58\nTax 1.49\nTotal 16.07\nVISA 16.07",
            "PHILZ COFFEE\nOct 22, 2026\nMint Mojito 5.75\nSUBTOTAL 5.75\nTAX 0.59\nAMOUNT DUE 6.34\nCASH 10.00\nCHANGE 3.66",
            "Trader Joe's #127\n10-07-26\nBananas 0.29\nTOTAL\n8.41\nBALANCE DUE 8.41"]:
    print(' ocr', parse_receipt_text(txt))
print(ns.budget_body({'Rent': D('1')}, {'Rent': D('2')}, notes={'Rent': 'Needs review'})[:6])
