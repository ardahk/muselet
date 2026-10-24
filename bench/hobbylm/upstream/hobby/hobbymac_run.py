"""Live evaluation of the Hobby Mac helper on the sealed Grok test set.

  PYTORCH_ENABLE_MPS_FALLBACK=1 .venv-hf-reference/bin/python backend/capability/macos_agent/hobbymac_run.py --model trained|untrained [--ids C01,D03]
MODEL: every action. HARNESS: setup (record state, quit Calculator), validation, execution, teardown (restore brightness,
volume, mute, dark mode; quit apps / close Finder windows it opened; delete test screenshots; cancel test timers).
CHECKERS: calc_checker (display), brightness get, osascript (volume, dark mode, frontmost app, Finder path), files.
Invalid actions are rejected and not retried; TYPE spells x, ×, ÷, − as Calculator keys.
"""
from __future__ import annotations

import os

import argparse
import hashlib
import json
import re
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from hobbymac_data import SYSTEM, SYSTEM_V2, state_text, user_turn  # noqa: E402
import calendar_tool as CAL  # noqa: E402
from datetime import datetime  # noqa: E402
from zoneinfo import ZoneInfo  # noqa: E402
LOCAL_TZ = 'Asia/Kolkata'
TEST_CAL = 'Hobby Test'
from mcp_client import MCP, SERVER_COMMIT  # noqa: E402

ROOT = Path(os.environ.get('HOBBY_HOME', Path(__file__).resolve().parents[1]))  # repo root
WORK = ROOT / 'data'
STOP = WORK / 'STOP'
SHOTS = WORK / 'test-screenshots'
SYSTEM_IN_USE = SYSTEM  # round-1/2 adapters; round 3 switches to SYSTEM_V2 in main()
MAX_PROPOSALS = 6
APPS = {'calculator': 'Calculator', 'notes': 'Notes', 'calendar': 'Calendar', 'finder': 'Finder', 'music': 'Music', 'reminders': 'Reminders'}
FOLDERS = {'downloads': 'Downloads', 'desktop': 'Desktop', 'documents': 'Documents'}
DEVICE_KEYS = {'BRIGHTNESS_DOWN', 'BRIGHTNESS_UP', 'VOLUME_DOWN', 'VOLUME_UP', 'MUTE'}
KEYS_OK = re.compile(r'^[0-9.+\-*/=]+$')
ACTION = re.compile(r'^\s*(?:(OPEN)\s+(\w+)|(TYPE)\s+([0-9.+\-*/=×÷−xX ]*[0-9=])|(KEY)\s+([A-Za-z_]+)|(DARK_MODE)\s+(ON|OFF)\b|(FOLDER)\s+(\w+)'
                    r'|(TIMER)\s+(\d+)|(SCREENSHOT|DONE|UNKNOWN)\b)(.*)$', re.I)


def sh(*a):
    return subprocess.run(list(a), capture_output=True, text=True, timeout=30).stdout.strip()


def osa(s):
    return sh('osascript', '-e', s)


def running(app):
    return subprocess.run(['pgrep', '-x', app], capture_output=True).returncode == 0


def display():
    d = json.loads(sh(str(WORK / 'calc_checker')))
    return (d['display'] or '').replace('‎', '').strip() if d['running'] else None


def bright():
    return json.loads(sh(str(WORK / 'brightness'), 'get'))['brightness']


def vol():
    return int(osa('output volume of (get volume settings)')), osa('output muted of (get volume settings)') == 'true'


def dark():
    return osa('tell application "System Events" to tell appearance preferences to get dark mode') == 'true'


def front():
    return osa('tell application "System Events" to get name of first application process whose frontmost is true')


def finder_path():
    return osa('tell application "Finder" to if (count of windows) > 0 then get POSIX path of (target of front window as alias)')


def finder_windows():
    return int(osa('tell application "Finder" to count of windows') or 0)


def as_num(s):
    try:
        return float((s or '').replace(',', ''))
    except ValueError:
        return None


def parse(raw):
    first = next((l for l in raw.splitlines() if l.strip()), '')
    ev = re.match(r'^\s*EVENT\s+(.+?)\s*$', first, re.I)
    if ev:
        return {'format_ok': True, 'first_line': first, 'kind': 'EVENT', 'arg': ev.group(1), 'clean': True}
    m = ACTION.match(first)
    if not m:
        return {'format_ok': False, 'clean': False, 'first_line': first}
    g = m.groups()
    trailing = (g[13] or '').strip()
    base = {'format_ok': True, 'first_line': first}
    if g[0]:
        return base | {'kind': 'OPEN', 'arg': g[1], 'clean': not trailing}
    if g[2]:
        k = re.sub(r'\s+', '', g[3]).replace('×', '*').replace('÷', '/').replace('−', '-').replace('x', '*').replace('X', '*')
        return base | {'kind': 'TYPE', 'arg': k, 'clean': not trailing}
    if g[4]:
        return base | {'kind': 'KEY', 'arg': g[5].upper(), 'clean': not trailing}
    if g[6]:
        return base | {'kind': 'DARK_MODE', 'arg': g[7].upper(), 'clean': not trailing}
    if g[8]:
        return base | {'kind': 'FOLDER', 'arg': g[9], 'clean': not trailing}
    if g[10]:
        return base | {'kind': 'TIMER', 'arg': g[11], 'clean': not trailing}
    return base | {'kind': g[12].upper(), 'arg': None, 'clean': trailing in ('', '.')}


def validate(p, calc_open):
    if not p['format_ok']:
        return 'invalid_format'
    k, a = p['kind'], p.get('arg')
    if k == 'OPEN':
        if a.lower() not in APPS:
            return 'out_of_scope'
        return 'invalid_state' if a.lower() == 'calculator' and calc_open else 'valid'
    if k == 'TYPE':
        return 'invalid_state' if not calc_open else ('valid' if KEYS_OK.match(a) else 'invalid_format')
    if k == 'KEY':
        return 'valid' if a in DEVICE_KEYS else 'invalid_format'
    if k == 'FOLDER':
        return 'valid' if a.lower() in FOLDERS else 'out_of_scope'
    if k == 'TIMER':
        return 'valid' if 1 <= int(a) <= 600 else 'invalid_format'
    if k == 'EVENT':
        return 'valid' if CAL.parse_event(a) else 'invalid_format'
    return 'valid'


def event_matches(got: str, exp: str) -> bool:
    """Fields compared after the same deterministic resolution: title words (>= 50% of expected words), date, time+zone, person."""
    g, e = CAL.parse_event(got), CAL.parse_event(exp.removeprefix('EVENT ').strip())
    if not g or not e:
        return False
    now = datetime.now(ZoneInfo(LOCAL_TZ))
    pg, pe = CAL.plan_event(got, now, LOCAL_TZ, lookup=lambda n: []), CAL.plan_event(exp.removeprefix('EVENT ').strip(), now, LOCAL_TZ, lookup=lambda n: [])
    if not pg or not pe or str(pg.problem or '').startswith('could not') or pg.start != pe.start:
        return False
    words = lambda t: {w for w in re.findall(r'[a-z0-9]+', t.lower()) if w not in ('with', 'and', 'the', 'a')}
    we, wg = words(e[0]), words(g[0])
    if not we or len(we & wg) / len(we) < .5:
        return False
    return (g[3].lower() == e[3].lower()) or (g[3].lower() in ('none', '') and e[3].lower() in ('none', ''))


def snapshot():
    return {'bright': bright(), 'vol': vol(), 'dark': dark(), 'front': front(), 'finder_windows': finder_windows(),
            'running': {a: running(a) for a in APPS.values()}}


def trial(h, mcp, item):
    tid, kind, req, expected = item
    t0 = time.perf_counter()
    if running('Calculator'):  # setup: clear and quit Calculator so every trial starts with it closed
        r = mcp.call('macos-use_open_application_and_traverse', {'identifier': 'Calculator'})
        mcp.call('macos-use_press_key_and_traverse', {'pid': int(r['fields']['pid']), 'keyName': 'Escape'})
        osa('quit app "Calculator"')
        time.sleep(1)
    s0 = snapshot()
    pid, steps, last, stop, done_actions, timers, shots, events = None, [], None, None, [], [], [], []
    try:
        for i in range(MAX_PROPOSALS):
            co = running('Calculator')
            b, (v, m) = bright(), vol()
            state = state_text(co, display() if co else None, round(b * 100), v, m, front(), dark())
            u = user_turn(req, state, last)
            g = h.complete(SYSTEM_IN_USE, u)
            p = parse(g['raw'])
            status = validate(p, co)
            act = ' '.join(x for x in (p.get('kind'), p.get('arg')) if x) if p['format_ok'] else f'(unparseable: "{p["first_line"][:40]}")'
            rec = {'i': i, 'state': state, 'user_turn': u, 'raw': g['raw'], 'parsed': p, 'validation': status, 'action': act,
                   'prompt_tokens': g['prompt_tokens'], 'total_tokens': g['total_tokens'], 'seconds': g['seconds']}
            steps.append(rec)
            if p['format_ok'] and p['kind'] in ('DONE', 'UNKNOWN'):
                stop = 'model_' + p['kind'].lower()
                break
            if status == 'out_of_scope':
                stop = 'out_of_scope'
                break
            if last and last[0] == act and (last[1].startswith('rejected') or 'nothing changed' in last[1]):
                stop = 'no_progress_loop'
                break
            if status != 'valid':
                last = (act, 'rejected (not allowed in this state).')
                continue
            if STOP.exists():
                raise KeyboardInterrupt('STOP file')
            k, a = p['kind'], p.get('arg')
            if k == 'OPEN' and a.lower() == 'calculator':
                r = mcp.call('macos-use_open_application_and_traverse', {'identifier': 'Calculator'})
                pid = int(r['fields']['pid'])
                res = 'Calculator opened.'
            elif k == 'OPEN':
                sh('open', '-a', APPS[a.lower()]); time.sleep(1.5)
                res = f'{APPS[a.lower()]} opened.' if front() == APPS[a.lower()] else 'nothing changed.'
            elif k == 'TYPE':
                pid = pid or int(sh('pgrep', '-x', 'Calculator').split()[0])
                for _ in range(3):  # harness fix (2026-10-20): keys were dropped when typed before Calculator was frontmost/ready
                    if front() == 'Calculator':
                        break
                    mcp.call('macos-use_open_application_and_traverse', {'identifier': 'Calculator'})
                time.sleep(.5)
                before = display()
                mcp.call('macos-use_type_and_traverse', {'pid': pid, 'text': a})
                after = display()
                res = f'display changed from {before} to {after}.' if after != before else 'nothing changed on the display.'
            elif k == 'KEY':
                if a.startswith('BRIGHTNESS'):
                    bb = bright(); sh(str(WORK / 'brightness'), 'down' if a.endswith('DOWN') else 'up'); ba = bright()
                    res = f'brightness changed from {round(bb * 100)}% to {round(ba * 100)}%.' if ba != bb else 'nothing changed.'
                elif a == 'MUTE':
                    osa('set volume output muted true'); res = 'sound muted.'
                else:
                    vb = vol()[0]; sh(str(WORK / 'media_key'), a.lower()); time.sleep(.4); va = vol()[0]
                    res = f'volume changed from {vb}% to {va}%.' if va != vb else 'nothing changed.'
            elif k == 'DARK_MODE':
                osa(f'tell application "System Events" to tell appearance preferences to set dark mode to {"true" if a == "ON" else "false"}')
                res = f'dark mode turned {a.lower()}.'
            elif k == 'FOLDER':
                sh('open', str(Path.home() / FOLDERS[a.lower()])); time.sleep(1.2)
                res = f'Finder opened the {FOLDERS[a.lower()]} folder.'
            elif k == 'EVENT':
                plan = CAL.plan_event(a, datetime.now(ZoneInfo(LOCAL_TZ)), LOCAL_TZ, lookup=lambda n: [])  # tests never read real Contacts
                okc, uid = CAL.create_event(plan, TEST_CAL, LOCAL_TZ, with_invite=False) if plan and not str(plan.problem or '').startswith('could not') else (False, '')
                events.append({'arg': a, 'title': plan.title if plan else None, 'start': plan.start.isoformat() if plan and okc else None,
                               'who': plan.who if plan else None, 'created': okc, 'problem': plan.problem if plan else 'unparseable'})
                res = 'event added to the calendar.' if okc else f'could not add the event ({plan.problem if plan else "unparseable"}).'
            elif k == 'TIMER':
                timers.append(int(a))  # test mode: recorded, not scheduled
                res = f'timer set for {int(a)} minutes.'
            else:  # SCREENSHOT
                SHOTS.mkdir(parents=True, exist_ok=True)
                f = SHOTS / f'{tid}-{i}.png'
                sh('screencapture', '-x', str(f))
                shots.append(f)
                res = 'screenshot saved.' if f.exists() else 'nothing changed.'
            done_actions.append(act)
            rec['result'] = res
            last = (act, res)
        else:
            stop = 'max_proposals'
        final = {'display': display() if running('Calculator') else None, 'bright': bright(), 'vol': vol(), 'dark': dark(),
                 'front': front(), 'finder_path': finder_path() if finder_windows() > s0['finder_windows'] else None,
                 'timers': timers, 'screenshots': [str(x) for x in shots if x.exists()], 'events': events,
                 'calendar_readback': [CAL.find_event(TEST_CAL, e['title']) for e in events if e.get('created')]}
    finally:  # teardown: restore everything the trial may have changed
        sh(str(WORK / 'brightness'), 'set', str(s0['bright']))
        osa(f'set volume output volume {s0["vol"][0]}')
        osa(f'set volume output muted {"true" if s0["vol"][1] else "false"}')
        osa(f'tell application "System Events" to tell appearance preferences to set dark mode to {"true" if s0["dark"] else "false"}')
        while finder_windows() > s0['finder_windows']:
            osa('tell application "Finder" to close front window')
        for app, was in s0['running'].items():
            if not was and app not in ('Finder', 'Calculator') and running(app):
                osa(f'quit app "{app}"')
        for x in shots:
            x.unlink(missing_ok=True)
        for e in events:  # delete test events
            if e.get('title'):
                CAL.osa(f'tell application "Calendar" to tell calendar "{TEST_CAL}" to delete (every event whose summary is "{e["title"].replace(chr(34), chr(39))}")')
    said_done = stop == 'model_done'
    executed = [a for a in done_actions]
    exp = expected.strip()
    if kind == 'calc':
        typed = [a[5:] for a in executed if a.startswith('TYPE ')]
        correct = as_num(final['display']) is not None and abs(as_num(final['display']) - float(exp)) < 0.006
        completed = said_done and correct
        clean = completed and bool(typed) and all(t.endswith('=') for t in typed)
    elif kind == 'none':
        correct = completed = clean = bool(steps) and steps[0]['parsed'].get('kind') == 'UNKNOWN'
    elif kind == 'event':
        correct = len(events) == 1 and events[0]['created'] and event_matches(events[0]['arg'], exp) and bool(final['calendar_readback'] and final['calendar_readback'][0])
        completed = clean = said_done and correct
    else:
        want = {'device': f'KEY {exp}', 'dark': exp, 'app': exp, 'folder': exp, 'timer': exp, 'screenshot': 'SCREENSHOT'}[kind]
        right_action = [a.upper() for a in executed] == [want.upper()]
        effect = {'device': lambda: {'KEY BRIGHTNESS_DOWN': final['bright'] < s0['bright'], 'KEY BRIGHTNESS_UP': final['bright'] > s0['bright'] or s0['bright'] >= 1,
                                     'KEY VOLUME_DOWN': final['vol'][0] < s0['vol'][0], 'KEY VOLUME_UP': final['vol'][0] > s0['vol'][0] or s0['vol'][0] == 100,
                                     'KEY MUTE': final['vol'][1]}[want],
                  'dark': lambda: final['dark'] == (want.endswith('ON')),
                  'app': lambda: final['front'].lower() == want.split()[1].lower(),
                  'folder': lambda: bool(final['finder_path']) and final['finder_path'].rstrip('/').endswith(want.split()[1]),
                  'timer': lambda: final['timers'] == [int(want.split()[1])],
                  'screenshot': lambda: len(final['screenshots']) == 1}[kind]()
        correct = right_action and effect
        completed = clean = said_done and correct
    return {'id': tid, 'kind': kind, 'request': req, 'expected': exp, 'stop': stop, 'executed': executed, 'final': final, 'start': s0,
            'correct_outcome': correct, 'completed': completed, 'clean': clean, 'said_done': said_done,
            'proposals': len(steps), 'seconds_total': time.perf_counter() - t0, 'steps': steps}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--model', choices=['trained', 'untrained'], required=True)
    ap.add_argument('--ids', default='')
    ap.add_argument('--set', default='sealed', choices=['sealed', 'old30'])
    ap.add_argument('--runtime', default='torch', choices=['torch', 'mlx'])
    ap.add_argument('--round', default='r1', choices=['r1', 'r2', 'r3', 'r4'], help='test set')
    ap.add_argument('--adapter', default=None, choices=['r1', 'r2', 'r3', 'r4'], help='which trained adapter (default: same as --round)')
    a = ap.parse_args()
    if a.set == 'sealed':
        tsv = 'hobbymac-sealed-test.tsv' if a.round == 'r1' else f'hobbymac-sealed-test-{a.round}.tsv'
        rows = [l.split('\t') for l in (WORK / 'frozen' / tsv).read_text().splitlines() if l.strip()]
        items = [(r[0].strip(), r[1].strip(), r[2].strip(), r[3].strip()) for r in rows]
    else:
        old = json.loads((WORK / 'frozen' / 'calc-tasks.json').read_text())['held_out']
        items = [(f'O{i:02d}', 'calc', q, str(ans)) for i, (q, ans) in enumerate([x for xs in old.values() for x in xs], 1)]
    if a.ids:
        keep = set(a.ids.split(','))
        items = [x for x in items if x[0] in keep]
    global SYSTEM_IN_USE
    ad = a.adapter or a.round
    SYSTEM_IN_USE = SYSTEM_V2 if ad in ('r3', 'r4') else SYSTEM
    if a.runtime == 'mlx':  # same decisions as torch (checked 203/203 for r1), much faster
        from mlx_runtime import MlxHobby
        h = MlxHobby(WORK / f'hobbymac-lora-{ad}-ab.npz') if a.model == 'trained' else MlxHobby()
    elif a.model == 'trained':
        from torch_runtime import TorchHobby
        res = json.loads((WORK / ('hobbymac-train-results.json' if ad == 'r1' else f'hobbymac-train-results-{ad}.json')).read_text())
        h = TorchHobby(WORK / ('hobbymac-lora.pt' if ad == 'r1' else f'hobbymac-lora-{ad}.pt'), res['adapter_sha256'])
    else:
        from torch_runtime import TorchHobby
        h = TorchHobby()
    tag = (a.model if a.model == 'untrained' else f'trained-{ad}') + ('-mlx' if a.runtime == 'mlx' else '')
    out = WORK / 'runs' / f'hobbymac-{a.set}-{a.round}-{tag}-{time.strftime("%Y%m%d-%H%M%S")}'
    out.mkdir(parents=True)
    mcp = MCP()
    results = []
    try:
        for it in items:
            r = trial(h, mcp, it)
            results.append(r)
            print(r['id'], r['kind'], repr(r['request'][:42]), [s['action'] for s in r['steps']], '| expected', r['expected'], '|',
                  ('COMPLETED' + (' clean' if r['clean'] else '')) if r['completed'] else '-', flush=True)
    except KeyboardInterrupt as e:
        print('interrupted', e)
    finally:
        mcp.close()
        (out / 'results.json').write_text(json.dumps({'model': tag, 'round': a.round, 'set': a.set, 'identity': h.identity, 'macos_use_commit': SERVER_COMMIT,
                                                      'runner_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                                                      'results': results}, indent=1, ensure_ascii=False, default=str) + '\n')
    print(out)


if __name__ == '__main__':
    main()
