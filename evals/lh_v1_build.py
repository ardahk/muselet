"""Build evals/lh_v1.jsonl: the long-horizon live E2E suite (lead-authored).

Run: python3 evals/lh_v1_build.py
Fixture cases need the local fixture server (`python -m bench.fixtures.server --port 8777`).
Strict pass = every `check` passes (final state only, never the agent's reply); `milestones` are
diagnostic partial credit. Version: lh-v1.0.
"""

import json
from pathlib import Path

FIX = "http://127.0.0.1:8777"
SUITE_VERSION = "lh-v1.0"

FIXTURE_UP = {"shell": f"curl -sf {FIX}/api/health", "equals": "ok"}
SAFARI_OFF = {"applescript": 'application "Safari" is running', "equals": "false"}
TEXTEDIT_OFF = {"applescript": 'application "TextEdit" is running', "equals": "false"}
NUMBERS_OFF = [{"applescript": 'application id "com.apple.iWork.Numbers" is running', "equals": "false"},
               {"applescript": 'application id "com.apple.Numbers" is running', "equals": "false"}]
NO_FINDER_WINDOWS = {"applescript": 'tell application "Finder" to count Finder windows', "equals": "0"}
SAFARI_QUIT = {"applescript": 'if application "Safari" is running then tell application "Safari" to quit'}
TEXTEDIT_TEARDOWN = [
    {"applescript": 'if application "TextEdit" is running then tell application "TextEdit" to close '
                    '(every document whose path is missing value) saving no'},
    {"applescript": 'if application "TextEdit" is running then tell application "TextEdit" to quit'},
]
MARKER = {"shell": 'mkdir -p "{{sandbox}}" && touch "{{sandbox}}/.case_start"'}


def reset(case_id):
    return {"shell": f"curl -sf -X POST '{FIX}/api/reset?case={case_id}'"}


def open_safari(path):
    """Open the fixture page in a fresh Safari; fail setup unless exactly one window with one tab shows it."""
    url = FIX + path
    return {"shell": (
        f"open -a Safari '{url}' || exit 1\n"
        "for i in $(seq 1 60); do\n"
        "  u=$(osascript -e 'tell application \"Safari\" to if (count of documents) > 0 then "
        "return URL of front document' 2>/dev/null)\n"
        f"  case \"$u\" in {FIX}*) break;; esac\n"
        "  sleep 0.25\n"
        "done\n"
        "osascript -e 'tell application \"Safari\" to activate'\n"
        "sleep 1\n"
        "n=$(osascript -e 'tell application \"Safari\" to count windows')\n"
        "t=$(osascript -e 'tell application \"Safari\" to count tabs of window 1')\n"
        "u=$(osascript -e 'tell application \"Safari\" to return URL of front document')\n"
        f"[ \"$n\" = \"1\" ] && [ \"$t\" = \"1\" ] && case \"$u\" in {FIX}*) exit 0;; esac\n"
        "echo \"unexpected Safari state windows=$n tabs=$t url=$u\"; exit 1")}


def grade(case_id):
    return {"shell": f"curl -sf {FIX}/api/grade/{case_id}", "equals": "PASS"}


def milestones(case_id, names):
    return [{"name": n, "shell": f"curl -sf {FIX}/api/milestone/{case_id}/{n}", "equals": "PASS"} for n in names]


TEXTEDIT_APPLESCRIPT = "\n".join([
    'if application "TextEdit" is running then',
    '  tell application "TextEdit"',
    '    set out to ""',
    "    repeat with d in documents",
    "      set out to out & (text of d) & linefeed",
    "    end repeat",
    "    return out",
    "  end tell",
    "end if",
    'return ""'])


def _dump_then_py(applescript: str, py: str, *args: str) -> str:
    """Shell: AppleScript output -> temp file -> python verifier (argv[1] = file) printing PASS/FAIL."""
    extra = "".join(f" {a}" for a in args)
    return (f"d=$(mktemp)\nosascript > \"$d\" <<'OSA'\n{applescript}\nOSA\n"
            f"python3 - \"$d\"{extra} <<'PY'\n{py}PY\nrm -f \"$d\"")


def textedit_contains(*needles):
    py = ("import sys,re\n"
          "t=open(sys.argv[1]).read().lower()\n"
          f"needles={list(needles)!r}\n"
          "ok=all(re.search(n, t) for n in needles)\n"
          "print('PASS' if ok else 'FAIL text=' + ' '.join(t.split())[:300])\n")
    return {"shell": _dump_then_py(TEXTEDIT_APPLESCRIPT, py), "equals": "PASS"}


TEXTEDIT_HAS_DOC = {"name": "textedit_doc_exists", "shell": (
    "osascript -e 'if application \"TextEdit\" is running then tell application \"TextEdit\" to return "
    "(count of documents) > 0' -e 'return false'"), "equals": "true"}


def web_case(cid, category, start, utterance, names, *, confirm=True, require_confirm=False, timeout=420,
             extra_check=None, textedit=False, turns=None):
    pre = [FIXTURE_UP, SAFARI_OFF] + ([TEXTEDIT_OFF] if textedit else [])
    case = {
        "id": cid, "suite": SUITE_VERSION, "tier": "LH", "category": category, "grade": "screen",
        "timeout_s": timeout, "precondition": pre, "setup": [reset(cid), open_safari(start)],
        "check": extra_check if extra_check else [grade(cid)],
        "milestones": milestones(cid, names) + ([TEXTEDIT_HAS_DOC] if textedit else []),
        "teardown": [SAFARI_QUIT] + (TEXTEDIT_TEARDOWN if textedit else []),
        "confirm_reply": True if confirm else None,
        "document_apps": ["Safari"] + (["TextEdit"] if textedit else []),
        "expect_outcome": "ok",
    }
    if require_confirm:
        case["require_confirm"] = True
    if turns:
        case["turns"] = turns
    else:
        case["utterance"] = utterance
    return case


CASES = [
    web_case("lh-mart-two-items", "web", "/mart",
             "Add two bananas and a gallon of whole milk to my cart.",
             ["bananas_added", "bananas_qty_2", "milk_gallon_added", "milk_qty_1", "no_extras", "no_order"]),
    web_case("lh-mart-aaa", "web", "/mart",
             "Add two packs of triple A batteries to my cart.",
             ["aaa_added", "aaa_qty_2", "no_extras", "no_order"]),
    web_case("lh-mart-cheapest-beans", "web", "/mart",
             "Find the cheapest coffee beans on this site and add them to my cart.",
             ["browsed_coffee", "breakfast_added", "qty_1", "no_extras", "no_order"]),
    web_case("lh-mart-pancakes", "web", "/mart",
             "I'm making pancakes. Add eggs, whole milk and butter to my cart, one of each.",
             ["eggs_1", "whole_milk_1", "butter_1", "no_extras", "no_order"]),
    web_case("lh-mart-checkout", "web", "/mart",
             "Buy a dozen large eggs and ship them to Jane Doe, 12 Main Street, Springfield, 62704.",
             ["eggs_added", "reached_checkout", "order_placed", "items_ok", "name_ok", "address_ok"],
             require_confirm=True),
    web_case("lh-mart-followup", "multiturn", "/mart", None,
             ["turn1_house_blend", "beans_qty_2", "filters_1", "no_extras", "no_order"],
             turns=[{"utterance": "Add the house blend coffee beans to my cart.", "confirm_reply": True,
                     "wait_s": 1.0},
                    {"utterance": "Actually, make it two bags, and add a pack of coffee filters too.",
                     "confirm_reply": True, "wait_s": 1.0}]),
    web_case("lh-forms-volunteer", "web", "/forms/volunteer",
             "Fill out this volunteer form for me. My name is Alex Rivera, email alex dot rivera at example dot "
             "com, phone 555 0142. I'm a medium shirt, and I can do the morning shift on Saturdays and Sundays. "
             "Then submit it.",
             ["submitted", "single_submission", "first_name", "last_name", "email", "phone", "shirt_size", "shift",
              "days"]),
    web_case("lh-mail-reply", "web", "/mail",
             "Open the latest email from Jon Snow and reply saying winter is not coming.",
             ["opened_latest", "sent_one", "right_thread", "to_ok", "body_ok"], require_confirm=True),
    web_case("lh-mail-compose", "web", "/mail",
             "Email sam at example dot com with the subject lunch on Friday, and ask if he's free for lunch on "
             "Friday at noon.",
             ["sent_one", "to_ok", "subject_ok", "body_ok"], require_confirm=True),
    web_case("lh-wiki-founder", "web", "/wiki/quiz/q1",
             "Answer the question on this page. You can look it up on this wiki.",
             ["visited_city", "visited_founder", "answered", "correct"]),
    web_case("lh-wiki-taller", "web", "/wiki/quiz/q2",
             "Answer the question on this page. You can look it up on this wiki.",
             ["visited_varn", "visited_oskel", "answered", "correct"]),
    web_case("lh-bank-starbucks-textedit", "cross-app", "/bank/statement?page=1",
             "Add up all my Starbucks charges on this statement and write the total in a new TextEdit document.",
             ["page2", "page3"], textedit=True, extra_check=[textedit_contains(r"30\.15")]),
    web_case("lh-mail-offsite-textedit", "cross-app", "/mail",
             "Find Priya's email about the offsite and write the date, time and place in a new TextEdit document.",
             ["opened_offsite", "no_mail_sent"], textedit=True,
             extra_check=[textedit_contains(r"nov(ember)?\.? ?12|11/12", r"9:30", r"harbou?r room")]),
]

# ---------- native apps (no fixture server) ----------

STRAY_GROCERIES = ('for d in "$HOME/Documents" "$HOME/Desktop" "$HOME/Downloads" '
                   '"$HOME/Library/Mobile Documents/com~apple~TextEdit/Documents"; do '
                   'for f in "$d"/groceries.* "$d"/Groceries.*; do [ -e "$f" ] && '
                   '[ "$f" -nt "{{sandbox}}/.case_start" ] && echo "$f"; done; done; true')

CASES.append({
    "id": "lh-textedit-groceries-save", "suite": SUITE_VERSION, "tier": "LH", "category": "native", "grade": "screen",
    "timeout_s": 600,
    "utterance": "Open TextEdit, write a grocery list with eggs, milk and bread on separate lines, and save it as "
                 "groceries in my Muselet Sandbox folder.",
    "precondition": [TEXTEDIT_OFF],
    "setup": [MARKER],
    "check": [{"shell": (
        'f=$(ls "{{sandbox}}"/groceries.* "{{sandbox}}"/Groceries.* 2>/dev/null | head -1)\n'
        'if [ -z "$f" ]; then echo "FAIL no file in sandbox"; exit 0; fi\n'
        'd=$(mktemp)\ntextutil -convert txt -stdout "$f" > "$d" 2>/dev/null\n'
        "python3 - \"$d\" <<'PY'\n"
        "import sys\n"
        "lines=[l.strip().lower().lstrip('-*\\u2022 0123456789.)').strip() for l in open(sys.argv[1]).read()"
        ".splitlines() if l.strip()]\n"
        "ok=all(any(l==w or l.startswith(w+' ') for l in lines) for w in ('eggs','milk','bread'))\n"
        "print('PASS' if ok else 'FAIL lines=%s' % lines)\n"
        "PY\nrm -f \"$d\""), "equals": "PASS"}],
    "forbid": [{"shell": STRAY_GROCERIES, "contains": "groceries"}],
    "milestones": [
        TEXTEDIT_HAS_DOC,
        {"name": "text_written", **textedit_contains("eggs", "milk", "bread")},
        {"name": "file_in_sandbox", "shell": 'ls "{{sandbox}}"/groceries.* "{{sandbox}}"/Groceries.* >/dev/null 2>&1 '
                                              '&& echo yes || echo no', "equals": "yes"},
    ],
    "teardown": TEXTEDIT_TEARDOWN + [
        {"applescript": 'if application "TextEdit" is running then tell application "TextEdit" to close '
                        '(every document whose path contains "MuseletSandbox") saving no'},
        {"shell": STRAY_GROCERIES.replace('echo "$f"', 'rm -f "$f"')},
    ],
    "confirm_reply": True, "document_apps": ["TextEdit"], "expect_outcome": "ok",
})

INBOX_FILES = {"pdfs": ["report-q3.pdf", "invoice-0423.pdf", "manual.pdf"],
               "images": ["beach.jpg", "family.jpg", "receipt-scan.jpg"],
               "notes": ["todo.txt", "ideas.txt", "meeting-notes.txt"]}
_ALL_INBOX = [f for fs in INBOX_FILES.values() for f in fs]
_ORGANIZE_PY = (
    "import os,sys\n"
    f"want={INBOX_FILES!r}\n"
    "root=os.path.expanduser(sys.argv[1])\n"
    "top={x.lower(): x for x in os.listdir(root) if not x.startswith('.')}\n"
    "def content(d):\n"
    "    p=os.path.join(root, top.get(d, d))\n"
    "    return {x for x in os.listdir(p) if not x.startswith('.')} if os.path.isdir(p) else None\n"
    "part=sys.argv[2] if len(sys.argv) > 2 else 'all'\n"
    "if part == 'folders': ok=all(d in top and os.path.isdir(os.path.join(root, top[d])) for d in want)\n"
    "elif part in want: ok=content(part) == set(want[part])\n"
    "else: ok=set(top) == set(want) and all(content(d) == set(fs) for d, fs in want.items())\n"
    "print('PASS' if ok else 'FAIL top=%s %s' % (sorted(top), {d: sorted(content(d) or []) for d in want}))\n")


def organize_check(part):
    return {"shell": f"python3 - \"{{{{sandbox}}}}/inbox\" {part} <<'PY'\n{_ORGANIZE_PY}PY", "equals": "PASS"}


STRAY_INBOX = ('for d in "$HOME/Documents" "$HOME/Desktop" "$HOME/Downloads"; do for f in '
               + " ".join(_ALL_INBOX) + '; do [ -e "$d/$f" ] && [ "$d/$f" -nt "{{sandbox}}/.case_start" ] && '
               'echo "$d/$f"; done; done; true')

CASES.append({
    "id": "lh-finder-organize", "suite": SUITE_VERSION, "tier": "LH", "category": "native", "grade": "screen",
    "timeout_s": 600,
    "utterance": "In the inbox folder inside my Muselet Sandbox folder, make folders called pdfs, images and notes, "
                 "and move each file into the right one.",
    "precondition": [NO_FINDER_WINDOWS],
    "setup": [MARKER, {"shell": 'rm -rf "{{sandbox}}/inbox" && mkdir -p "{{sandbox}}/inbox" && cd "{{sandbox}}/inbox" '
                                '&& for f in ' + " ".join(_ALL_INBOX) + '; do printf "muselet fixture %s\\n" "$f" > '
                                '"$f"; done'}],
    "check": [organize_check("all")],
    "forbid": [{"shell": STRAY_INBOX, "contains": "/"}],
    "milestones": [{"name": "folders_exist", **organize_check("folders")},
                   {"name": "pdfs_moved", **organize_check("pdfs")},
                   {"name": "images_moved", **organize_check("images")},
                   {"name": "notes_moved", **organize_check("notes")}],
    "teardown": [{"shell": STRAY_INBOX.replace('echo "$d/$f"', 'rm -f "$d/$f"')},
                 {"shell": 'rm -rf "{{sandbox}}/inbox"'}],
    "confirm_reply": True, "expect_outcome": "ok",
})

_NUMBERS_DUMP = "\n".join([
    'set out to ""',
    *[line for app_id in ("com.apple.iWork.Numbers", "com.apple.Numbers") for line in (
        f'if application id "{app_id}" is running then',
        f'  tell application id "{app_id}"',
        "    repeat with d in documents",
        "      repeat with s in sheets of d",
        "        repeat with t in tables of s",
        "          repeat with c in cells of t",
        "            set v to value of c",
        "            if v is not missing value then",
        '              set f to ""',
        "              try",
        "                set f to formula of c",
        "              end try",
        '              if f is missing value then set f to ""',
        '              set out to out & (name of c) & "|" & (v as text) & "|" & f & linefeed',
        "            end if",
        "          end repeat",
        "        end repeat",
        "      end repeat",
        "    end repeat",
        "  end tell",
        "end if")],
    "return out"])
_NUMBERS_PY = (
    "import sys,re\n"
    "rows=[l.split('|',2) for l in open(sys.argv[1]).read().splitlines() if l.count('|')>=2]\n"
    "vals=[(n.strip(), v.strip(), f.strip()) for n,v,f in rows]\n"
    "def num(v):\n"
    "    v=v.replace(',','').replace('$','').strip()\n"
    "    try: return float(v)\n"
    "    except ValueError: return None\n"
    "nums=[num(v) for _,v,_ in vals]\n"
    "labels=' '.join(v.lower() for _,v,_ in vals)\n"
    "part=sys.argv[2] if len(sys.argv)>2 else 'all'\n"
    "ok_labels=all(w in labels for w in ('rent','food','transport'))\n"
    "ok_nums=all(x in nums for x in (1200.0,450.0,150.0))\n"
    "ok_total=any('sum' in f.lower() and num(v)==1800.0 for _,v,f in vals)\n"
    "ok={'labels':ok_labels,'numbers':ok_nums,'total':ok_total}.get(part, ok_labels and ok_nums and ok_total)\n"
    "print('PASS' if ok else 'FAIL labels=%s nums=%s total=%s cells=%s' % (ok_labels, ok_nums, ok_total, "
    "vals[:12]))\n")


def numbers_check(part):
    return {"shell": _dump_then_py(_NUMBERS_DUMP, _NUMBERS_PY, part), "equals": "PASS"}


CASES.append({
    "id": "lh-numbers-budget", "suite": SUITE_VERSION, "tier": "LH", "category": "native", "grade": "screen",
    "timeout_s": 600,
    "utterance": "Make a new Numbers spreadsheet with rent 1200, food 450 and transport 150, and a total under them "
                 "using a sum formula.",
    "precondition": NUMBERS_OFF,
    "check": [numbers_check("all")],
    "milestones": [{"name": "labels", **numbers_check("labels")}, {"name": "numbers", **numbers_check("numbers")},
                   {"name": "sum_total", **numbers_check("total")}],
    "teardown": [{"applescript": f'if application id "{a}" is running then tell application id "{a}" to close '
                                 '(every document whose name starts with "Untitled") saving no'}
                 for a in ("com.apple.iWork.Numbers", "com.apple.Numbers")]
                + [{"applescript": f'if application id "{a}" is running then tell application id "{a}" to quit'}
                   for a in ("com.apple.iWork.Numbers", "com.apple.Numbers")],
    "confirm_reply": True, "document_apps": ["Numbers"], "expect_outcome": "ok",
})

# ---------- online (real websites; reported separately, skipped by --offline) ----------

SAFARI_FRONT = ("osascript -e 'if application \"Safari\" is running then tell application \"Safari\" to return "
                "(URL of front document) & \" | \" & (name of front document)' -e 'return \"\"' | "
                "tr '[:upper:]' '[:lower:]'")
PLAYING_JXA = (
    "const se = Application('System Events');\n"
    "let out = 'no';\n"
    "if (se.processes.whose({name: 'Safari'}).length) {\n"
    "  const proc = se.processes.byName('Safari');\n"
    "  if (proc.windows.length) {\n"
    "    const queue = [proc.windows[0]]; let seen = 0;\n"
    "    while (queue.length && seen < 2500) {\n"
    "      const el = queue.shift(); seen += 1;\n"
    "      try {\n"
    "        if (el.role() === 'AXButton') {\n"
    "          const label = [el.description(), el.name(), el.title()].join(' ');\n"
    "          if (/^\\s*pause\\b/i.test(label)) { out = 'yes'; break; }\n"
    "        }\n"
    "      } catch (e) {}\n"
    "      try { for (const child of el.uiElements()) queue.push(child); } catch (e) {}\n"
    "    }\n"
    "  }\n"
    "}\n"
    "out;")

CASES.append({
    "id": "lh-yt-jazz", "suite": SUITE_VERSION, "tier": "LH", "category": "online", "grade": "screen", "online": True,
    "timeout_s": 420, "utterance": "Open YouTube in Safari and play some jazz.",
    "precondition": [SAFARI_OFF, {"shell": "curl -sI -m 5 https://www.youtube.com | head -1", "contains": "HTTP"}],
    "check": [{"shell": SAFARI_FRONT, "contains": "youtube.com/watch"}, {"shell": SAFARI_FRONT, "contains": "jazz"}],
    "milestones": [{"name": "on_youtube", "shell": SAFARI_FRONT, "contains": "youtube.com"},
                   {"name": "playing", "jxa": PLAYING_JXA, "equals": "yes"}],
    "teardown": [SAFARI_QUIT], "confirm_reply": True, "document_apps": ["Safari"], "expect_outcome": "ok",
})

CASES.append({
    "id": "lh-wikipedia-ggb-textedit", "suite": SUITE_VERSION, "tier": "LH", "category": "online", "grade": "screen",
    "online": True, "timeout_s": 480,
    "utterance": "Look up when the Golden Gate Bridge opened on Wikipedia in Safari, then write the year in a new "
                 "TextEdit document.",
    "precondition": [SAFARI_OFF, TEXTEDIT_OFF,
                     {"shell": "curl -sI -m 5 https://en.wikipedia.org | head -1", "contains": "HTTP"}],
    "check": [textedit_contains(r"1937")],
    "milestones": [{"name": "on_wikipedia", "shell": SAFARI_FRONT, "contains": "wikipedia.org"}, TEXTEDIT_HAS_DOC],
    "teardown": [SAFARI_QUIT] + TEXTEDIT_TEARDOWN, "confirm_reply": True,
    "document_apps": ["Safari", "TextEdit"], "expect_outcome": "ok",
})


if __name__ == "__main__":
    out = Path(__file__).with_name("lh_v1.jsonl")
    ids = [c["id"] for c in CASES]
    assert len(ids) == len(set(ids)), "duplicate ids"
    out.write_text("".join(json.dumps(c, ensure_ascii=False) + "\n" for c in CASES))
    print(f"wrote {len(CASES)} cases to {out}")
