"""Synthetic training turns for the Hobby Mac helper (Calculator + brightness/volume), from templates.

Each example is ONE decision: (request, screen state, last action/result) -> action. Traces:
  calc:   Calculator closed -> OPEN Calculator ; display shows something -> TYPE <a op b => ; display = answer -> DONE
  device: any state -> KEY <name> ; after the key changed the setting -> DONE
  none:   any state -> UNKNOWN
Keys always stop at '=' so the calculator, not the model, does the arithmetic.
Requests resembling any test request (word-set Jaccard >= 0.5) are removed before training (see filter_against).
"""
from __future__ import annotations

import json
import random
import re
from pathlib import Path

SYSTEM = ("You are Hobby, an offline helper on a Mac. Each turn you see the user's request and the current state, "
          "and choose exactly ONE next action.\nAllowed actions:\n"
          "OPEN <app>  (apps: Calculator, Notes, Calendar, Finder, Music, Reminders)\n"
          "TYPE <keys>  (calculator keys only: digits . + - * / =)\n"
          "KEY BRIGHTNESS_DOWN | KEY BRIGHTNESS_UP | KEY VOLUME_DOWN | KEY VOLUME_UP | KEY MUTE\n"
          "DARK_MODE ON | DARK_MODE OFF\n"
          "FOLDER Downloads | FOLDER Desktop | FOLDER Documents\n"
          "TIMER <minutes>\n"
          "SCREENSHOT\n"
          "DONE  (the request is complete)\n"
          "UNKNOWN  (the request is not something these actions can do)\n"
          "For maths, open the calculator, type the numbers and the operation, and let it compute. Reply with the action only.")

SYSTEM_V2 = ("You are Hobby, an offline helper on a Mac. Each turn you see the user's request and the current state, "
          "and choose exactly ONE next action.\nAllowed actions:\n"
          "OPEN <app>  (apps: Calculator, Notes, Calendar, Finder, Music, Reminders)\n"
          "TYPE <keys>  (calculator keys only: digits . + - * / =)\n"
          "KEY BRIGHTNESS_DOWN | KEY BRIGHTNESS_UP | KEY VOLUME_DOWN | KEY VOLUME_UP | KEY MUTE\n"
          "DARK_MODE ON | DARK_MODE OFF\n"
          "FOLDER Downloads | FOLDER Desktop | FOLDER Documents\n"
          "TIMER <minutes>\n"
          "SCREENSHOT\n"
          "EVENT <title> | <day> | <time> [timezone] | <person name or email, or none>  (add a calendar event)\n"
          "DONE  (the request is complete)\n"
          "UNKNOWN  (the request is not something these actions can do)\n"
          "For maths, open the calculator, type the numbers and the operation, and let it compute. Reply with the action only.")

SYSTEM_V1 = SYSTEM

ONES = 'zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen'.split()
TENS = {20: 'twenty', 30: 'thirty', 40: 'forty', 50: 'fifty', 60: 'sixty', 70: 'seventy', 80: 'eighty', 90: 'ninety'}


def words(n: int) -> str:
    sep = random.choice(['-', ' ', ' '])
    if n < 20:
        return ONES[n]
    if n < 100:
        return TENS[n // 10 * 10] + ('' if n % 10 == 0 else sep + ONES[n % 10])
    if n < 1000:
        r = random.random()
        if n % 100 and r < .3:  # Indian shorthand: 150 -> "one fifty", 225 -> "two twenty five"
            return f'{ONES[n // 100]} {words(n % 100)}' if n % 100 >= 10 else f'{ONES[n // 100]} hundred {ONES[n % 100]}'
        h = ('a hundred' if n // 100 == 1 and r < .5 else f'{ONES[n // 100]} hundred')
        return h if n % 100 == 0 else (f'{h} and {words(n % 100)}' if r < .6 else f'{h} {words(n % 100)}')
    if n % 1000 == 0 and n < 10000:
        return f'{ONES[n // 1000]} thousand'
    return str(n)


def fmt(x: float) -> str:
    x = round(x, 8)
    return str(int(x)) if x == int(x) else f'{x:.10g}'


def num_text(n, rng):
    if isinstance(n, int) and n <= 999 and rng.random() < .25:
        return words(n)
    if n == 12 and rng.random() < .5:
        return 'a dozen'
    if n in (24, 36, 48) and rng.random() < .5:
        return {24: 'two dozen', 36: 'three dozen', 48: 'four dozen'}[n]
    if n == 100 and rng.random() < .5:
        return rng.choice(['hundred', 'a hundred', 'one hundred'])
    return fmt(n)


CALC = {  # op: list of templates; {a} {b} are operands in the order typed (a op b)
    '+': ['add {a} and {b}', '{a} plus {b}', "what's {a} + {b}", 'sum of {a} and {b}', '{a} and {b} together', 'total of {a} and {b}',
          'add {b} to {a}', 'put {a} and {b} together', 'i have {a} and get {b} more, how many now?', 'whats {a}+{b}',
          '{a} rupees plus {b} rupees', 'I walked {a} km and then {b} km, how far in total?', 'what do {a} and {b} make',
          '{a} and {b} extra, total', '{a} plus another {b}', 'ticket {a} plus fee {b}, total', 'add {b} more to {a}'],
    '-': ['{a} minus {b}', 'subtract {b} from {a}', 'take {b} away from {a}', 'knock {b} off {a}', '{b} fewer than {a}',
          'how much is {a} take away {b}', 'I had {a} and spent {b}, how much left?', 'difference between {a} and {b}',
          'how much more is {a} than {b}', '{a} - {b} pls', 'reduce {a} by {b}', 'I paid {a} for something that cost {b}, change?',
          'how much less is {b} than {a}', 'take {b} off {a}', '{b} short of {a}', '{b} fewer than {a}', 'pull {b} out of {a}',
          'deduct {b} from {a}', 'remove {b} from {a}, what remains', 'what is {b} less than {a}', '{a} minus {b} kitna',
          'had {a}, used {b}, how many left', 'gave {a}, it cost {b}, change?', 'from {a} remove {b}', 'how far is {b} from {a}'],
    '*': ['{a} times {b}', 'multiply {a} by {b}', '{a} into {b}', "what's {a} x {b}", 'product of {a} and {b}',
          '{a} boxes of {b} each, how many in total?', '{a} pens at {b} each, total cost?', '{b} per day for {a} days',
          '{a} multiplied by {b}', 'double {b}', 'triple {b}', '{b} each, ordered {a}, total', '{a} people paying {b} each, total',
          '{a} into {b} kitna', '{a} rows of {b}', '{b} rupees a kg, {a} kg, how much', '{a} weeks of {b} each, total'],
    '/': ['{a} divided by {b}', 'divide {a} by {b}', 'split {a} among {b} people', '{a} shared by {b}', 'how many {b}s in {a}',
          '{a} dinner bill, {b} of us, how much each?', '{a} into {b} equal parts', 'half of {a}', 'a third of {a}', '{a}/{b}',
          'spent {a} on {b} things, cost of each?', 'average of {a} over {b} days'],
}
DEVICE = {
    'BRIGHTNESS_DOWN': ['the glare is killing my eyes', 'eyes burning, screen too strong', "it's night and the screen is too bright", 'too much light from the screen',
                        'the display is too bright', 'bright screen at night, lower it', 'dim my screen', 'make the screen darker', "screen's blinding me", 'lower the brightness', 'screen is hurting my eyes',
                        'turn brightness down a bit', 'reduce screen brightness', 'darker please', 'bright screen, tone it down'],
    'BRIGHTNESS_UP': ["I'm outside and can't see the screen", "can't read, it's too dark", 'screen looks dim', 'make it brighter so I can read', 'brighten my screen', "I can't see the screen, too dark", 'increase brightness', 'make the display brighter',
                      'turn up the brightness', 'screen is too dim', 'more light on the screen pls', 'brightness up'],
    'VOLUME_DOWN': ['people are sleeping, softer please', 'the sound is way too high', 'turn it down a notch', 'bring the volume lower', 'turn the volume down', "it's too loud", 'lower the sound', 'quieter please', 'reduce volume a bit',
                    'volume down', 'the music is blasting', 'not so loud'],
    'VOLUME_UP': ['the video is too quiet', 'cant hear the call', 'pump up the volume', 'a bit louder', 'turn it up', 'barely audible', 'louder please', 'increase the volume', 'volume up', 'make it louder',
                  'sound is too low', 'raise the volume'],
    'MUTE': ['call starting, mute everything', 'boss is on the phone, silence it', 'zero sound now', 'mute it quick', 'mute', 'mute the sound', 'silence my mac', 'turn off the sound', 'no sound please', 'shut the audio off',
             'quiet, call starting', 'kill the volume completely'],
}
NONE = ["what's the weather today", 'send a message to mom', 'open youtube', 'tell me a joke', 'who won the match',
        'add 2 and 3 then multiply by 4', 'play some music on spotify', 'set an alarm for 6am tomorrow', 'what time is it in London',
        'book a cab', 'translate hello to hindi', 'email my boss', 'what is 5 plus 3 times 2 minus 1', 'open a website',
        "how's it going", 'turn on wifi', 'search google for biryani', 'who invented the light bulb', 'make me a spreadsheet',
        'what is the volume of a sphere', 'dark chocolate recipes', 'open instagram', 'call my brother', 'how bright is the sun',
        'download a movie', 'what day is it', 'write an essay on india', 'turn off bluetooth', 'order pizza', 'is it going to rain']
NEAR = {  # sound like a skill but are not doable with these actions
    'w': ['what does {k} mean', 'define {k}', 'who invented {k2}', 'history of {k2}', 'is my {k3} broken', 'my {k3} stopped working',
          'play {song} on spotify', 'play {song} loud on youtube', 'open {site}', 'open {app} please', 'open a new tab in {app}',
          'delete my {files}', 'rename my {files}', 'move my {files} to the trash', 'how many minutes until {event}', 'how long till {event}',
          'average of {a}, {b} and {c}', 'what is {a} plus {b} times {c}', '{a} + {b} - {c}', 'add {a}, {b} and {c}', 'calculate my {money}',
          'set the brightness on my phone', 'turn up the volume on the tv', 'dark mode on my phone', 'set an alarm for {a} am'],
    'k': ['dark matter', 'brightness', 'volume', 'mute', 'a timer', 'dark mode', 'a screenshot', 'the calculator'],
    'k2': ['the calculator', 'the screenshot', 'dark mode', 'the timer', 'music'],
    'k3': ['volume button', 'brightness key', 'screen', 'calculator app', 'keyboard'],
    'song': ['some bollywood songs', 'arijit singh', 'lofi beats', 'my playlist', 'old hindi songs'],
    'site': ['flipkart.com', 'amazon.in', 'youtube.com', 'google', 'zomato', 'my bank website'],
    'app': ['chrome', 'safari', 'whatsapp', 'spotify', 'slack', 'zoom', 'photoshop'],
    'files': ['screenshots', 'downloads', 'desktop files', 'documents', 'notes'],
    'event': ['my flight', 'the match', 'lunch', 'the meeting', 'new year'],
    'money': ['taxes', 'emi', 'salary after tax', 'gst', 'loan interest']}


NEAR_SHARE = .6  # round 2; round 3 lowers it (over-refusal seen in round 2)


def near_miss(rng):
    t = rng.choice(NEAR['w'])
    return t.format(k=rng.choice(NEAR['k']), k2=rng.choice(NEAR['k2']), k3=rng.choice(NEAR['k3']), song=rng.choice(NEAR['song']),
                    site=rng.choice(NEAR['site']), app=rng.choice(NEAR['app']), files=rng.choice(NEAR['files']), event=rng.choice(NEAR['event']),
                    money=rng.choice(NEAR['money']), a=rng.randint(2, 99), b=rng.randint(2, 99), c=rng.randint(2, 99))
APPS = {
    'Notes': ['open notes', 'need to write something quick', 'take a quick note', 'where are my notes', 'notes app please', 'open the notes thing'],
    'Calendar': ['am I busy this week', 'open calendar', 'show me my calendar', 'do I have meetings today', 'check my dates', 'calendar pls'],
    'Finder': ['open finder', 'show my files', 'I want to browse my files', 'open a finder window', 'file browser please'],
    'Music': ['apple music', 'open apple music app', 'start the music app', 'open music', 'open the music app', 'I want my songs', 'apple music please', 'show my music library'],
    'Reminders': ['open reminders', 'show my to-do list', 'my reminders app', 'open my todo app', "what's on my reminders"],
}
FOLDERS = {
    'Downloads': ['open downloads', 'find the stuff I downloaded', 'show my downloads folder', 'downloads folder pls', 'the thing I just downloaded'],
    'Desktop': ['the desktop folder please', 'files on my desktop', 'open the desktop one', 'open desktop folder', 'show me the files on my desktop', 'desktop folder', 'whats on my desktop folder'],
    'Documents': ['documents please', 'my docs', 'open the documents one', 'open documents', 'my documents folder', 'show documents', 'where are my docs', 'documents folder please'],
}
DARK = {'ON': ['use the black theme', 'make the windows dark', 'dark theme for night', 'switch the look to dark', 'turn on dark mode', 'dark mode please', 'make everything dark', 'too white, switch to dark', 'night mode on', 'night time, darken the theme'],
        'OFF': ['use the white theme', 'back to the light look', "it's sunny, light theme please", 'switch the look to light', 'turn off dark mode', 'light mode please', 'switch back to light', 'back to the bright theme', 'disable dark mode', 'too dark, light theme']}
TIMER = [('timer for {n} minutes', None), ('set a {n} minute timer', None), ('remind me in {n} mins', None), ('{n} min timer', None),
         ('wake me up in {n} minutes', None), ('countdown {n} minutes', None), ('timer {n}m', None),
         ('half an hour timer', 30), ('remind me in an hour', 60), ('timer for one and a half hours', 90), ('quarter of an hour timer', 15),
         ('set a timer for {w} minutes', None), ('remind me in two hours', 120),
         ('{h} hours timer', 'h'), ('remind me in {h} hrs', 'h'), ('timer {h}h', 'h'), ('ping me after {h} hours', 'h'),
         ('timer for {h}.5 hours', 'h5'), ('{h} and a half hours', 'h5'), ('an hour and a half', 90), ('timer for 1 hr', 60),
         ('in {h} hr {m} min', 'hm'), ('{n} mins timer', None), ('timer for {w} mins', None),
         ('timer {h} hour {m} minutes', 'hm'), ('an hour and {m} min', 'h1m'), ('set timer {h} hr {m} min', 'hm'), ('{h}h {m}m timer', 'hm'),
         ('timer of {h} hours', 'h'), ('set a {h} hr timer', 'h'), ('{h} hour timer', 'h'), ('timer for {hw} hours', 'hw'), ('{hw} hour timer', 'hw'),
         ('remind me in {hw} hrs', 'hw'), ('timer for {hw} hour {m} mins', 'hwm')]
SHOT = ['take a screenshot', 'screenshot please', 'grab my screen', 'capture the screen', 'snap the screen', 'save a picture of my screen']


def state_text(calc_open: bool, display: str | None, bright: int, vol: int, muted: bool, front: str = 'Finder', dark: bool = False) -> str:
    lines = [f'Calculator: open, display shows {display}' if calc_open else 'Calculator: not open', f'Front app: {front}',
             f'Brightness: {bright}%  Volume: {vol}%{" (muted)" if muted else ""}', f'Dark mode: {"on" if dark else "off"}']
    return '\n'.join(lines)


def user_turn(req: str, state: str, last: tuple[str, str] | None) -> str:
    u = f'Request: {req}\n\nState:\n{state}'
    if last:
        u += f'\n\nLast action: {last[0]}. Result: {last[1]}'
    return u + '\n\nNext action:'


def calc_example(rng):
    op = rng.choice('+-*/')
    t = rng.choice(CALC[op])
    if '/' == op:
        b = rng.choice([2, 3, 4, 5, 6, 8, 10, 12, 15, 20, 25])
        a = b * rng.randint(2, 120) if rng.random() < .8 else round(rng.uniform(5, 500), rng.choice([0, 1]))
        if t.startswith('half'):
            b = 2
        if t.startswith('a third'):
            b = 3
            a = 3 * rng.randint(2, 99)
    elif op == '*':
        a, b = rng.randint(2, 40), rng.randint(2, 250)
        if t.startswith('double'):
            a = 2
        if t.startswith('triple'):
            a = 3
    else:
        a, b = rng.randint(2, 2000), rng.randint(1, 900)
        if op == '-' and rng.random() < .85 and b > a:
            a, b = b, a
        if rng.random() < .1:
            a, b = round(a + rng.random(), 1), round(b + rng.random(), 1)
    if op == '*' and 'double' not in t and 'triple' not in t and '{a} boxes' not in t and '{a} pens' not in t and rng.random() < .3:
        pass
    req = t.format(a=num_text(a, rng), b=num_text(b, rng))
    if rng.random() < .15:
        req = req.capitalize()
    if rng.random() < .1:
        req += '?'
    keys = f'{fmt(a)}{op}{fmt(b)}='
    ans = fmt(eval(keys[:-1]))
    return req, keys, ans


EVENT_T = ['book a call with {who} {day} at {time}', 'schedule a meeting with {who} on {day} at {time}', 'set up a {topic} with {who} {day} {time}',
           'put a {topic} with {who} on my calendar for {day} at {time}', 'calendar: {topic} {day} {time} with {who}', 'add {topic} {day} at {time}',
           'block {day} {time} for {topic}', 'meeting {day} {time} {who}', '{topic} with {who} at {time} {day} pls', 'remind me of {topic} on {day} at {time} in my calendar',
           'create an event {topic} {day} {time}', 'can you book {day} {time} with {who} for {topic}',
           'lock in a {topic} w/ {who} {day} {time}', '{topic} w/ {who} {day} {time}', 'pencil in {topic} {day} {time}',
           'put {topic} {day} {time}', 'set {topic} for {day} {time}', 'add {topic} w/ {who} {day} {time}', 'need a {topic} with {who} {day} {time}',
           'squeeze in a {topic} {day} {time}', 'get {topic} on the cal {day} {time}', '{day} {time} {topic} with {who}', 'quick {topic} {day} {time} with {who}']
EV_WHO = ['Naval', 'Priya', 'Rahul', 'Ananya', 'Dev', 'Sara', 'Arjun', 'Meera', 'John', 'Kavya', 'the team', 'mom']
EV_TOPIC = ['call', 'catch-up', 'sync', 'interview', 'demo', 'review', 'dentist appointment', 'standup', 'investor call', '1:1', 'coffee chat', 'design review']
EV_DAY = ['today', 'tomorrow', 'tmrw', 'monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday', 'next monday', 'next friday',
          'mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'next tue', 'DATE', 'DATE', 'DATE', 'DATE']
MONTHS3 = ['jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec']
EV_TZ = ['', '', '', ' UTC', ' IST', ' PST', ' EST', ' GMT', ' CET', ' SGT']


def event_example(rng):
    who = rng.choice(EV_WHO + [None, None])
    email = None
    if who and who not in ('the team', 'mom') and rng.random() < .35:
        email = f'{who.lower()}@{rng.choice(["gmail.com", "hotmail.com", "outlook.com", "company.in"])}'
    topic = rng.choice(EV_TOPIC)
    day = rng.choice(EV_DAY)
    if day == 'DATE':
        dn, mo = rng.randint(1, 28), rng.choice(MONTHS3)
        day = f'{dn} {mo}' if rng.random() < .6 else f'{mo} {dn}'
    h, m = rng.randint(1, 12), rng.choice([0, 0, 0, 15, 30, 45])
    ap = rng.choice(['am', 'pm', 'pm'])
    tz = rng.choice(EV_TZ)
    spoken_time = (f'{h}{ap}' if m == 0 else f'{h}:{m:02d} {ap}') + tz
    h24 = (h % 12) + (12 if ap == 'pm' else 0)
    t = rng.choice([x for x in EVENT_T if ('{who}' in x) == bool(who)] or EVENT_T)
    only_email = bool(email) and rng.random() < .6
    req = t.format(who=email if only_email else (who or ''), day=day, time=spoken_time, topic=topic).replace('  ', ' ').strip()
    if email and email not in req:
        req += rng.choice([f', email {email}', f' ({email})', f', their mail is {email}'])
    if '{topic}' not in t:  # title may only use words present in the request
        topic = 'call' if 'call' in t else 'meeting' if 'meeting' in t else 'event'
    shown = email if only_email else who  # the title uses exactly what the person wrote
    title = f'{topic[0].upper() + topic[1:]} with {shown}' if shown else topic[0].upper() + topic[1:]
    action = f'EVENT {title} | {day} | {h24:02d}:{m:02d}{tz} | {email or who or "none"}'
    return req, action


FRONTS = ['Finder', 'Google Chrome', 'Safari', 'Notes', 'Mail', 'Visual Studio Code', 'Slack', 'Music', 'Calendar', 'Terminal']


def make(n_calc=3000, n_dev=1100, n_none=1100, n_app=500, n_folder=400, n_dark=400, n_timer=600, n_shot=250, seed=7, n_event=0):
    rng = random.Random(seed)
    random.seed(seed)
    out = []

    def st():
        co = rng.random() < .3
        return dict(calc_open=co, display=rng.choice(['0', fmt(rng.randint(1, 999))]) if co else None, bright=rng.choice(range(10, 101, 6)),
                    vol=rng.choice(range(0, 101, 6)), muted=rng.random() < .1, front=rng.choice(FRONTS), dark=rng.random() < .5)

    def add(kind, req, s, last, action):
        if rng.random() < .15:
            req = req.capitalize()
        out.append((kind, req, user_turn(req, state_text(**s), last), action))

    def two_step(kind, req, action, result, mutate):
        s = st()
        if rng.random() < .55:
            add(kind, req, s, None, action)
        else:
            mutate(s)
            add(kind, req, s, (action, result), 'DONE')

    for _ in range(n_calc):
        req, keys, ans = calc_example(rng)
        s = st()
        stage = rng.random()
        if stage < .3:
            s.update(calc_open=False, display=None)
            add('calc', req, s, None, 'OPEN Calculator')
        elif stage < .7:
            s.update(calc_open=True, display=rng.choice(['0', '0', fmt(rng.randint(1, 999))]), front='Calculator')
            last = ('OPEN Calculator', 'Calculator opened.') if s['display'] == '0' and rng.random() < .6 else None
            add('calc', req, s, last, f'TYPE {keys}')
        else:
            prev = rng.choice(['0', fmt(rng.randint(1, 999))])
            s.update(calc_open=True, display=ans, front='Calculator')
            add('calc', req, s, (f'TYPE {keys}', f'display changed from {prev} to {ans}.'), 'DONE')
    for _ in range(n_dev):
        key = rng.choice(list(DEVICE))
        req = rng.choice(DEVICE[key]) + rng.choice(['', '', ' please', ' pls', '!'])
        s = st()
        if rng.random() < .55:
            add('device', req, s, None, f'KEY {key}')
        else:
            if key.startswith('BRIGHT'):
                nb = max(6, s['bright'] + (6 if key.endswith('UP') else -6)); res = f'brightness changed from {s["bright"]}% to {nb}%.'; s['bright'] = nb
            elif key == 'MUTE':
                res = 'sound muted.'; s['muted'] = True
            else:
                nv = max(0, min(100, s['vol'] + (6 if key.endswith('UP') else -6))); res = f'volume changed from {s["vol"]}% to {nv}%.'; s['vol'] = nv
            add('device', req, s, (f'KEY {key}', res), 'DONE')
    for _ in range(n_app):
        app = rng.choice(list(APPS))
        two_step('app', rng.choice(APPS[app]), f'OPEN {app}', f'{app} opened.', lambda s, a=app: s.update(front=a))
    for _ in range(n_folder):
        f = rng.choice(list(FOLDERS))
        two_step('folder', rng.choice(FOLDERS[f]), f'FOLDER {f}', f'Finder opened the {f} folder.', lambda s: s.update(front='Finder'))
    for _ in range(n_dark):
        m = rng.choice(['ON', 'OFF'])
        two_step('dark', rng.choice(DARK[m]), f'DARK_MODE {m}', f'dark mode turned {m.lower()}.', lambda s, m=m: s.update(dark=m == 'ON'))
    for _ in range(n_timer):
        t, fixed = rng.choice(TIMER)
        hh, mm = rng.choice([1, 2, 3, 4, 5]), rng.choice([5, 10, 15, 20, 30, 45])
        n = rng.choice([1, 2, 3, 5, 7, 8, 10, 12, 15, 20, 25, 30, 35, 40, 45, 50, 55])
        if fixed == 'h':
            n = 60 * hh
        elif fixed == 'h5':
            n = 60 * hh + 30
        elif fixed == 'hm':
            n = 60 * hh + mm
        elif fixed == 'h1m':
            n = 60 + mm
        elif fixed == 'hw':
            n = 60 * hh
        elif fixed == 'hwm':
            n = 60 * hh + mm
        elif fixed:
            n = fixed
        req = t.format(n=n, w=words(n), h=hh, m=mm, hw=ONES[hh])
        two_step('timer', req, f'TIMER {n}', f'timer set for {n} minutes.', lambda s: None)
    for _ in range(n_shot):
        two_step('screenshot', rng.choice(SHOT), 'SCREENSHOT', 'screenshot saved to the Desktop.', lambda s: None)
    for _ in range(n_event):
        req, action = event_example(rng)
        s_ = st()
        if rng.random() < .6:
            add('event', req, s_, None, action)
        else:
            add('event', req, s_, (action, 'event added to the calendar.'), 'DONE')
    for _ in range(n_none):
        add('none', near_miss(rng) if rng.random() < NEAR_SHARE else rng.choice(NONE), st(), None, 'UNKNOWN')
    rng.shuffle(out)
    return out


def wordset(t):
    return {w for w in re.findall(r'[a-z]+|\d+', t.lower()) if len(w) > 1 or w.isdigit()}


def filter_against(examples, test_requests, thr=.5):
    tests = [wordset(t) for t in test_requests]
    keep, dropped = [], []
    for ex in examples:
        w = wordset(ex[1])
        if any(w and t and len(w & t) / len(w | t) >= thr for t in tests):
            dropped.append(ex[1])
        else:
            keep.append(ex)
    return keep, dropped


if __name__ == '__main__':
    ex = make()
    print(len(ex))
    for e in ex[:12]:
        print(e[0], '|', e[1], '|', e[3])
