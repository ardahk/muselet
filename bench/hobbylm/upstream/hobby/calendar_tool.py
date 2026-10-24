"""Calendar skill for Hobby: the model writes one structured action, plain code does the rest.

  EVENT <title> | <day> | <time> [timezone] | <person name or email, or "none">
  e.g. EVENT Call with Naval | Tuesday | 15:00 UTC | Naval
       EVENT Call with Naval | Tuesday | 15:00 UTC | naval@example.com

Code (deterministic, no model): resolve day+time+timezone to an exact datetime; find the email (an email in the action
wins; otherwise look the name up in Contacts, read-only; 0 or several matches -> ask the user); show a confirmation;
only on "yes" create the event in Apple Calendar (with the invite). A checker reads the event back.
"""
from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

DAYS = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
MONTHS = ['jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec']
TZ = {'utc': 'UTC', 'gmt': 'UTC', 'ist': 'Asia/Kolkata', 'pst': 'America/Los_Angeles', 'pdt': 'America/Los_Angeles', 'pt': 'America/Los_Angeles',
      'est': 'America/New_York', 'edt': 'America/New_York', 'et': 'America/New_York', 'cst': 'America/Chicago', 'ct': 'America/Chicago',
      'bst': 'Europe/London', 'uk': 'Europe/London', 'cet': 'Europe/Paris', 'sgt': 'Asia/Singapore', 'jst': 'Asia/Tokyo', 'aest': 'Australia/Sydney',
      'gst': 'Asia/Dubai'}
EMAIL = re.compile(r'^[\w.+-]+@[\w-]+(\.[\w-]+)+$')


@dataclass
class EventPlan:
    title: str
    start: datetime          # timezone-aware, in the requested zone
    minutes: int
    who: str | None          # what the model wrote (name or email)
    email: str | None = None
    email_source: str | None = None   # 'request' | 'contacts'
    problem: str | None = None        # set when the plan can't be completed without the user


def parse_event(arg: str) -> tuple[str, str, str, str] | None:
    parts = [p.strip() for p in arg.split('|')]
    if len(parts) == 3:
        parts.append('none')
    if len(parts) != 4 or not parts[0]:
        return None
    return tuple(parts)


def resolve_day(day: str, today: date) -> date | None:
    d = day.strip().lower().replace(',', ' ')
    if d in ('today', 'tonight'):
        return today
    if d in ('tomorrow', 'tmrw', 'tmr', 'tomorow', 'tommorow', 'tomoro'):
        return today + timedelta(days=1)
    m = re.fullmatch(r'(next\s+)?(mon|tue|wed|thu|fri|sat|sun)[a-z]*', d)
    if m:
        target = [x[:3] for x in DAYS].index(m.group(2))
        ahead = (target - today.weekday()) % 7
        if ahead == 0 or m.group(1):
            ahead = ahead or 7
        return today + timedelta(days=ahead)
    m = re.fullmatch(r'(\d{1,2})\s*(?:st|nd|rd|th)?\s+([a-z]{3})[a-z]*', d) or re.fullmatch(r'([a-z]{3})[a-z]*\s+(\d{1,2})(?:st|nd|rd|th)?', d)
    if m:
        a, b = m.groups()
        day_n, mon = (int(a), b) if a.isdigit() else (int(b), a)
        if mon in MONTHS:
            cand = date(today.year, MONTHS.index(mon) + 1, day_n)
            return cand if cand >= today else date(today.year + 1, cand.month, cand.day)
    m = re.fullmatch(r'(\d{1,2})[/-](\d{1,2})', d)  # day/month (Indian/UK order)
    if m:
        cand = date(today.year, int(m.group(2)), int(m.group(1)))
        return cand if cand >= today else date(today.year + 1, cand.month, cand.day)
    return None


def resolve_time(t: str, local_tz: str) -> tuple[int, int, ZoneInfo] | None:
    s = t.strip().lower()
    tz = ZoneInfo(local_tz)
    m = re.search(r'\b([a-z]{2,4})$', s)
    if m and m.group(1) in TZ:
        tz = ZoneInfo(TZ[m.group(1)])
        s = s[:m.start()].strip()
    if s in ('noon', 'midday'):
        return 12, 0, tz
    m = re.fullmatch(r'(\d{1,2})(?::|\.)?(\d{2})?\s*(am|pm)?', s)
    if not m:
        return None
    h, mi, ap = int(m.group(1)), int(m.group(2) or 0), m.group(3)
    if ap == 'pm' and h < 12:
        h += 12
    if ap == 'am' and h == 12:
        h = 0
    if h > 23 or mi > 59:
        return None
    return h, mi, tz


def osa(script: str) -> tuple[int, str]:
    p = subprocess.run(['osascript', '-e', script], capture_output=True, text=True, timeout=60)
    return p.returncode, (p.stdout or p.stderr).strip()


def contacts_lookup(name: str) -> list[tuple[str, str]]:
    """Read-only. Returns [(person name, email)] for people whose name contains `name`."""
    q = name.replace('"', '')
    osa('tell application "Contacts" to launch')  # the lookup fails with -600 if Contacts isn't running
    code, out = osa(f'''tell application "Contacts"
        set res to ""
        repeat with p in (every person whose name contains "{q}")
            repeat with e in (emails of p)
                set res to res & (name of p) & tab & (value of e) & linefeed
            end repeat
        end repeat
        return res
    end tell''')
    if code != 0:
        raise RuntimeError(f'Contacts lookup failed: {out}')
    return [tuple(l.split('\t', 1)) for l in out.splitlines() if '\t' in l]


def plan_event(arg: str, now: datetime, local_tz: str, lookup=contacts_lookup, minutes: int = 30) -> EventPlan | None:
    parts = parse_event(arg)
    if not parts:
        return None
    title, day, time_s, who = parts
    d = resolve_day(day, now.astimezone(ZoneInfo(local_tz)).date())
    t = resolve_time(time_s, local_tz)
    if not d or not t:
        return EventPlan(title, now, minutes, who, problem=f'could not understand the date/time "{day} {time_s}"')
    h, mi, tz = t
    plan = EventPlan(title, datetime(d.year, d.month, d.day, h, mi, tzinfo=tz), minutes, None if who.lower() == 'none' else who)
    if plan.who:
        if EMAIL.match(plan.who):
            plan.email, plan.email_source = plan.who.lower(), 'request'
        else:
            try:
                hits = sorted(set(lookup(plan.who)))
            except Exception:  # Contacts unavailable: fall back to asking the user
                hits = []
            if len(hits) == 1:
                plan.email, plan.email_source = hits[0][1], 'contacts'
            elif not hits:
                plan.problem = f'no email for "{plan.who}" in Contacts. Add it to the request, e.g. "| {plan.who.lower()}@example.com"'
            else:
                plan.problem = 'several contacts match: ' + ', '.join(f'{n} <{e}>' for n, e in hits[:5])
    return plan


def describe(plan: EventPlan, local_tz: str) -> str:
    loc = plan.start.astimezone(ZoneInfo(local_tz))
    s = f'"{plan.title}" on {plan.start:%a %d %b} at {plan.start:%H:%M} {plan.start.tzname()}'
    if plan.start.utcoffset() != loc.utcoffset():
        s += f' ({loc:%a %H:%M} your time)'
    s += f', {plan.minutes} min'
    if plan.email:
        s += f', inviting {plan.email}' + (' (from Contacts)' if plan.email_source == 'contacts' else '')
    return s


def as_literal(s: str) -> str:
    """Escape text for an AppleScript string literal (backslash first, then double quote)."""
    return s.replace('\\', '\\\\').replace('"', '\\"')


def create_event(plan: EventPlan, calendar: str, local_tz: str, with_invite: bool) -> tuple[bool, str]:
    loc = plan.start.astimezone(ZoneInfo(local_tz))
    title = as_literal(plan.title)
    inv = (f'\n            make new attendee at end of attendees of ev with properties {{email:"{plan.email}"}}'
           if with_invite and plan.email else '')
    code, out = osa(f'''set d to current date
        set day of d to 1
        set year of d to {loc.year}
        set month of d to {loc.month}
        set day of d to {loc.day}
        set hours of d to {loc.hour}
        set minutes of d to {loc.minute}
        set seconds of d to 0
        tell application "Calendar"
            tell calendar "{calendar}"
                set ev to make new event with properties {{summary:"{title}", start date:d, end date:(d + {plan.minutes} * minutes)}}{inv}
            end tell
            return uid of ev
        end tell''')
    return code == 0, out


def find_event(calendar: str, title: str) -> list[str]:
    """Checker (read-only): start dates of events with this exact title in the calendar."""
    t = as_literal(title)
    code, out = osa(f'''tell application "Calendar" to tell calendar "{calendar}"
        set res to ""
        repeat with ev in (every event whose summary is "{t}")
            set res to res & ((start date of ev) as «class isot» as string) & linefeed
        end repeat
        return res
    end tell''')
    return out.splitlines() if code == 0 else []


# ---------------------------------------------------------------- safety checks (2026-10-22)
# The model fills the form; plain code then cross-checks it against the user's own sentence. Exact copying (emails, explicit
# times) is done by code, not the model. Every change is reported to the user before they confirm.
import subprocess as _sp

EMAIL_ANY = re.compile(r'[\w.+-]+@[\w-]+(?:\.[\w-]+)+')
TIME_ANY = re.compile(r'\b(\d{1,2})(?:[:.](\d{2}))?\s*(am|pm)\b|\b([01]?\d|2[0-3])[:.](\d{2})\b', re.I)
DAY_ANY = re.compile(r'\b(today|tonight|tomorrow|tmrw|tmr|(?:next\s+)?(?:mon|tue|wed|thu|fri|sat|sun)[a-z]*|\d{1,2}\s*(?:st|nd|rd|th)?\s+[a-z]{3}[a-z]*'
                     r'|(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+\d{1,2})\b', re.I)
TZ_ANY = re.compile(r'\b(' + '|'.join(TZ) + r')\b', re.I)


def system_tz() -> str:
    """The Mac's own time zone (fix 5: was hard-coded to India)."""
    try:
        p = _sp.run(['readlink', '/etc/localtime'], capture_output=True, text=True).stdout.strip()
        return p.split('zoneinfo/')[-1] or 'UTC'
    except Exception:
        return 'UTC'


def harden(arg: str, request: str) -> tuple[str, list[str]]:
    """Fixes 1-3: cross-check the model's EVENT fields against the request. Returns (corrected arg, list of notes)."""
    notes = []
    emails = EMAIL_ANY.findall(request)
    raw = [p.strip() for p in arg.split('|')]
    if len(raw) > 4:  # extra field (e.g. an email written into its own slot): drop fields that are just an email
        kept = [x for x in raw if not EMAIL_ANY.fullmatch(x)] or raw
        if len(kept) == 3:
            kept.append(emails[0] if emails else 'none')
        if len(kept) == 4:
            notes.append('removed an extra field')
            arg = ' | '.join(kept)
    parts = parse_event(arg)
    if not parts:
        return arg, ['could not read the event the model wrote']
    title, day, time_s, who = parts
    # a person is only invited if you actually named them
    if who.lower() not in ('none', '') and not EMAIL_ANY.fullmatch(who) and who.lower() not in request.lower():
        notes.append(f'"{who}" is not in your sentence, so nobody is invited')
        title = re.sub(rf'\s+with\s+{re.escape(who)}\b', '', title, flags=re.I) or title
        who = 'none'
    # fix 1: an email in the request is copied exactly by code
    if len(emails) == 1:
        e = emails[0].lower()
        if who.lower() != e:
            notes.append(f'person set to {e} (copied from your sentence)')
            who = e
        for frag in re.findall(r'[\w.+-]+@[\w.-]*', title):
            if frag.lower() != e and e.startswith(frag.lower()):
                title = title.replace(frag, e)
    # fix 3: fields in the wrong slot -> take the day from the request if the model's day isn't a day
    if resolve_day(day, date.today()) is None:
        m = DAY_ANY.search(request)
        if m:
            notes.append(f'day taken from your sentence ("{m.group(0)}")')
            day = m.group(0)
    # fix 2: an explicit time in the request wins over the model's time (am/pm slips)
    ts = [m for m in TIME_ANY.finditer(request)]
    if len(ts) == 1:
        m = ts[0]
        if m.group(3):
            h = int(m.group(1)) % 12 + (12 if m.group(3).lower() == 'pm' else 0)
            mi = int(m.group(2) or 0)
        else:
            h, mi = int(m.group(4)), int(m.group(5))
        tzm = TZ_ANY.search(request)
        want = f'{h:02d}:{mi:02d}' + (f' {tzm.group(1).upper()}' if tzm else '')
        got = resolve_time(time_s, 'UTC')
        if not got or (got[0], got[1]) != (h, mi) or (tzm and tzm.group(1).lower() not in time_s.lower()):
            notes.append(f'time set to {want} (as you wrote it)')
            time_s = want
    return f'{title} | {day} | {time_s} | {who}', notes


def warnings(plan: 'EventPlan', day_text: str, now: datetime) -> list[str]:
    """Fixes 6-7: past times and 'Tuesday' said on a Tuesday."""
    w = []
    if plan.start <= now:
        w.append('that time has already passed')
    d = day_text.strip().lower()
    wd = [x[:3] for x in DAYS]
    if d[:3] in wd and not d.startswith('next') and wd.index(d[:3]) == now.weekday():
        w.append(f'today is {DAYS[now.weekday()].capitalize()}, so I picked NEXT {DAYS[now.weekday()].capitalize()}; say "today" if you meant today')
    if d.startswith('next') and (plan.start.date() - now.date()).days < 7:
        w.append(f'"{day_text}" could mean {plan.start:%a %d %b} or a week later; give the date if you meant the later one')
    return w
