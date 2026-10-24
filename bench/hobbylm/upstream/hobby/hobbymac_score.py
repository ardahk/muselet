"""Score hobbymac live runs against the frozen pass bar (hobbymac-pass-bar.json + amendment 1).
Usage: python3 hobbymac_score.py <runs/hobbymac-...>/results.json [more results.json ...]
"""
import os
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(os.environ.get('HOBBY_HOME', Path(__file__).resolve().parents[1]))  # repo root
BAR = {'calc': .90, 'device': .85, 'dark': .85, 'app': .85, 'folder': .85, 'timer': .85, 'screenshot': .85, 'event': .85, 'none': .80}


def score(path):
    d = json.loads(Path(path).read_text())
    rnd = d.get('round', 'r1')
    REGEX = json.loads((ROOT / ('data/hobbymac-regex-sealed.json' if rnd == 'r1' else f'data/hobbymac-regex-sealed-{rnd}.json')).read_text())
    by = defaultdict(lambda: defaultdict(int))
    steps = []
    for r in d['results']:
        b = by[r['kind']]
        b['n'] += 1
        b['completed'] += r['completed']
        b['clean'] += r['clean']
        b['correct_outcome'] += r['correct_outcome']
        b['said_done'] += r['said_done']
        steps += r['steps']
    rows, passed, passed75 = {}, True, True
    for k in BAR:
        if k not in by:
            continue
        b = by[k]
        metric = b['clean'] if k == 'calc' else b['completed']
        rate = metric / b['n']
        ok = rate >= BAR[k]
        if k == 'calc':
            ok = ok and rate >= REGEX['regex_correct'] / REGEX['n'] + .20
        ok75 = rate >= .75 and (k != 'calc' or rate >= REGEX['regex_correct'] / REGEX['n'] + .20)
        passed &= ok
        passed75 &= ok75
        rows[k] = {'n': b['n'], 'metric': 'clean completed' if k == 'calc' else ('first action UNKNOWN' if k == 'none' else 'completed'),
                   'score': metric, 'rate': round(rate, 3), 'bar': BAR[k], 'pass': ok, 'pass_owner_75': ok75, 'completed_any': b['completed'], 'said_done': b['said_done']}
    fmt = {'proposals': len(steps), 'format_ok': sum(s['parsed']['format_ok'] for s in steps), 'clean_format': sum(s['parsed'].get('clean', False) for s in steps),
           'rejected': sum(s['validation'] != 'valid' for s in steps), 'out_of_scope': sum(s['validation'] == 'out_of_scope' for s in steps),
           'mean_tokens': round(sum(s['total_tokens'] for s in steps) / max(1, len(steps))), 'max_tokens': max((s['total_tokens'] for s in steps), default=0),
           'mean_model_seconds': round(sum(s['seconds'] for s in steps) / max(1, len(steps)), 2),
           'total_seconds': round(sum(r['seconds_total'] for r in d['results']), 1)}
    return {'round': rnd, 'model': d['model'], 'identity': d['identity'], 'all_pass': passed, 'all_pass_owner_75': passed75, 'skills': rows, 'format': fmt, 'regex_calc': REGEX}


if __name__ == '__main__':
    for p in sys.argv[1:]:
        s = score(p)
        print(f"== {s['round']} {s['model']}  ALL PASS frozen bar: {s['all_pass']} | owner 75% bar: {s['all_pass_owner_75']}")
        for k, v in s['skills'].items():
            print(f"  {k:10} {v['score']:>3}/{v['n']:<3} ({v['rate']:.0%}) bar {v['bar']:.0%} {'PASS' if v['pass'] else 'fail'} | 75%: {'PASS' if v['pass_owner_75'] else 'fail'}")
        print('  ', s['format'])
        out = Path(p).parent / 'score.json'
        out.write_text(json.dumps(s, indent=1) + '\n')
