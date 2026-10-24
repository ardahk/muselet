"""Probe brain.advisor on variants of the Henderson household (not this household's wording/accounts)."""
import shutil, sys, json, tempfile, pathlib
sys.path.insert(0, 'ml/src')
from brain.advisor import core
from brain.advisor.brief import brief_markdown, clean_phrasing
from brain.advisor.scripts import numbers_review_script, notes_brief_script
SRC = pathlib.Path('evals/fixtures/advisor/henderson')
def variant(edit):
    d = pathlib.Path(tempfile.mkdtemp()) / 'h'; shutil.copytree(SRC, d); edit(d); return d
# 1. Same need, different wording: renovation instead of lake house
def notes(d):
    p = d / 'last_meeting_notes.txt'
    p.write_text(p.read_text().replace('Lake house', 'Kitchen remodel').replace(
        'They found a cabin near Lake Almanor. They want to put $120,000 down on the lake house next spring (target April 2027).',
        'They want to pay the $120,000 contractor deposit for the kitchen remodel next spring (target April 2027).'))
p = core.prep(core.load_household(variant(notes)))
print('1 renovation wording: excess', p['cash']['excess'], 'reserve', p['cash']['lake_house_reserve'])
print('  brief:', [l for l in brief_markdown(p).splitlines() if 'Lake house' in l or 'excess savings' in l])
# 2. Single filer
def single(d):
    j = json.loads((d / 'profile.json').read_text()); j['filing_status'] = 'single'; (d / 'profile.json').write_text(json.dumps(j))
try: core.prep(core.load_household(variant(single))); print('2 single: ok')
except Exception as e: print('2 single filer: prep raises', type(e).__name__, e)
# 3. 401(k) and checking account names
print('3 account_kind:', {a: core.account_kind(a) for a in ['Mark 401(k)', 'Elena 403(b)', 'Joint Checking', 'Mark HSA', 'Elena SEP IRA', 'Joint taxable brokerage']})
# 4. LLM phrasing smuggles numbers as words
print('4 phrasing kept:', clean_phrasing({'headline': 'They can convert about sixty thousand dollars this year.'})['headline'])
s = numbers_review_script(p)
print('5 review script:', [l.strip() for l in s.splitlines() if 'delete' in l])
print('  notes:', [l.strip() for l in notes_brief_script(p).splitlines() if 'delete' in l or 'every note' in l])
print('6 opportunities:', [(o['key'], o['impact_usd'], o['impact_kind']) for o in core.prep(core.load_household(SRC))['opportunities']])
