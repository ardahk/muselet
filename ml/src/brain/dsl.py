"""Parse the AGENTS.md action DSL into action dicts and serialize back.

Grammar (one action per line, max 5 per batch):
    skill <name> key=value ...
    press #<ref>
    type #<ref> "<text>" [enter]
    keys <combo>
    scroll #<ref> up|down|left|right [n]
    click <x>,<y> [right|double]
    open "<App Name>"
    url "<https://...>"
    script applescript|jxa|shell \"\"\"<code>\"\"\"
    wait <ms>
    ask|confirm|done|refuse "<text>"
    expect <predicate>    (attaches to the previous action)

predicates: title~"<t>" | focused #<r> | value #<r>="<t>" | app "<n>" | appears "<l>" | gone #<r>
"""

import re

MAX_BATCH = 5


class DSLError(ValueError):
    def __init__(self, msg: str, line: int):
        super().__init__(f"line {line}: {msg}")
        self.line = line
        self.msg = msg


def _err(msg, line):
    return DSLError(msg, line)


def _unquote(tok: str, line: int) -> str:
    if len(tok) >= 2 and tok[0] == '"' and tok[-1] == '"':
        body = tok[1:-1]
        return re.sub(r"\\(.)", lambda m: {"n": "\n", "t": "\t"}.get(m.group(1), m.group(1)), body)
    raise _err(f"expected quoted string, got {tok!r}", line)


def _coerce(tok: str):
    if len(tok) >= 2 and tok[0] == '"' and tok[-1] == '"':
        return _unquote(tok, 1)
    if tok == "true":
        return True
    if tok == "false":
        return False
    try:
        return int(tok)
    except ValueError:
        pass
    try:
        return float(tok)
    except ValueError:
        pass
    return tok


def _ref(tok: str, line: int) -> int:
    if not tok.startswith("#") or not tok[1:].isdigit():
        raise _err(f"expected #<ref>, got {tok!r}", line)
    return int(tok[1:])


def _tokenize(line: str, lineno: int) -> list[str]:
    """Whitespace split that keeps "quoted strings" (and \" escapes) whole."""
    toks, cur = [], []
    inq = False
    i, n = 0, len(line)
    while i < n:
        ch = line[i]
        if inq:
            if ch == "\\" and i + 1 < n:
                cur.append(ch)
                cur.append(line[i + 1])
                i += 2
                continue
            cur.append(ch)
            if ch == '"':
                inq = False
            i += 1
            continue
        if ch == '"':
            inq = True
            cur.append(ch)
        elif ch.isspace():
            if cur:
                toks.append("".join(cur))
                cur = []
        else:
            cur.append(ch)
        i += 1
    if inq:
        raise _err("unterminated quote", lineno)
    if cur:
        toks.append("".join(cur))
    return toks


_PRED_RE = re.compile(
    r'^(title~"(?:[^"\\]|\\.)*"|focused #\d+|value #\d+="(?:[^"\\]|\\.)*"|'
    r'app "(?:[^"\\]|\\.)*"|appears "(?:[^"\\]|\\.)*"|gone #\d+)$'
)


def parse_predicate(s: str, line: int) -> str:
    """Validate a predicate; returns the canonical string form."""
    t = s.strip()
    if not _PRED_RE.match(t):
        raise _err(f"bad expect predicate: {t!r}", line)
    return t


def parse(text: str) -> list[dict]:
    """Parse a DSL batch. Raises DSLError with .line set."""
    lines = text.split("\n")
    actions: list[dict] = []
    i = 0
    while i < len(lines):
        lineno = i + 1
        raw = lines[i]
        line = raw.strip()
        i += 1
        # '# <note>' comment lines and ``` fences are not actions
        if not line or line.startswith("#") or line.startswith("```"):
            continue

        # triple-quoted script block may span lines
        m = re.match(r'^script\s+(applescript|jxa|shell)\s+"""(.*)$', line)
        if m:
            lang, rest = m.group(1), m.group(2)
            if rest.endswith('"""') and len(rest) >= 3:
                code = rest[:-3]
            else:
                buf = [rest]
                while i < len(lines):
                    buf.append(lines[i])
                    i += 1
                    if '"""' in buf[-1]:
                        break
                joined = "\n".join(buf)
                if not joined.endswith('"""'):
                    raise _err("unterminated script block", lineno)
                code = joined[:-3]
            actions.append({"op": "script", "lang": lang, "code": code})
            continue

        toks = _tokenize(line, lineno)
        if not toks:
            continue
        op = toks[0]

        if op == "expect":
            pred = parse_predicate(line[len("expect"):].strip(), lineno)
            if not actions:
                raise _err("expect with no preceding action", lineno)
            actions[-1]["expect"] = pred
            continue
        if op == "skill":
            if len(toks) < 2:
                raise _err("skill needs a name", lineno)
            args = {}
            for kv in toks[2:]:
                if "=" not in kv:
                    raise _err(f"skill arg must be key=value, got {kv!r}", lineno)
                k, v = kv.split("=", 1)
                args[k] = _coerce(v)
            actions.append({"op": "skill", "name": toks[1], "args": args})
            continue
        if op == "press":
            if len(toks) != 2:
                raise _err("press #<ref>", lineno)
            actions.append({"op": "press", "ref": _ref(toks[1], lineno)})
            continue
        if op == "type":
            if len(toks) < 3:
                raise _err('type #<ref> "<text>" [enter]', lineno)
            enter = toks[-1] == "enter"
            str_toks = toks[2:-1] if enter else toks[2:]
            if not str_toks:
                raise _err("type needs text", lineno)
            text = " ".join(_unquote(t, lineno) for t in str_toks)
            actions.append({"op": "type", "ref": _ref(toks[1], lineno),
                            "text": text, "enter": enter})
            continue
        if op == "keys":
            if len(toks) != 2:
                raise _err("keys <combo>", lineno)
            actions.append({"op": "keys", "combo": toks[1]})
            continue
        if op == "scroll":
            if len(toks) not in (3, 4):
                raise _err("scroll #<ref> up|down [n]", lineno)
            direction = toks[2]
            if direction not in ("up", "down", "left", "right"):
                raise _err(f"bad direction {direction!r}", lineno)
            n = int(toks[3]) if len(toks) == 4 and toks[3].isdigit() else 3
            actions.append({"op": "scroll", "ref": _ref(toks[1], lineno),
                            "direction": direction, "n": n})
            continue
        if op == "click":
            if len(toks) < 2:
                raise _err("click <x>,<y> [right|double]", lineno)
            try:
                x, y = (float(v) for v in toks[1].split(","))
            except ValueError:
                raise _err(f"bad coords {toks[1]!r}", lineno)
            actions.append({"op": "click", "x": x, "y": y,
                            "right": "right" in toks[2:],
                            "double": "double" in toks[2:]})
            continue
        if op == "open":
            actions.append({"op": "open", "name": _unquote(toks[1], lineno)})
            continue
        if op == "url":
            actions.append({"op": "url", "url": _unquote(toks[1], lineno)})
            continue
        if op == "wait":
            if len(toks) != 2 or not toks[1].isdigit():
                raise _err("wait <ms>", lineno)
            actions.append({"op": "wait", "ms": int(toks[1])})
            continue
        if op in ("ask", "confirm", "done", "refuse"):
            key = {"ask": "question", "confirm": "summary",
                   "done": "summary", "refuse": "reason"}[op]
            if len(toks) != 2:
                raise _err(f'{op} "<text>"', lineno)
            actions.append({"op": op, key: _unquote(toks[1], lineno)})
            continue
        raise _err(f"unknown op {op!r}", lineno)

    n = len(actions)
    if n > MAX_BATCH:
        raise _err(f"batch has {n} actions (max {MAX_BATCH})", 1)
    return actions


def _q(s: str) -> str:
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n") + '"'


def serialize(actions: list[dict]) -> str:
    """Serialize action dicts back to DSL text."""
    lines = []
    for a in actions:
        op = a["op"]
        if op == "skill":
            line = "skill " + a["name"]
            for k, v in a.get("args", {}).items():
                if isinstance(v, bool):
                    v = "true" if v else "false"
                elif isinstance(v, str) and (not v or re.search(r'[\s"=]', v)):
                    v = _q(v)
                line += f" {k}={v}"
        elif op == "press":
            line = f"press #{a['ref']}"
        elif op == "type":
            line = f"type #{a['ref']} {_q(a['text'])}"
            if a.get("enter"):
                line += " enter"
        elif op == "keys":
            line = f"keys {a['combo']}"
        elif op == "scroll":
            line = f"scroll #{a['ref']} {a['direction']}"
            if a.get("n", 3) != 3:
                line += f" {a['n']}"
        elif op == "click":
            x, y = a["x"], a["y"]
            fmt = lambda v: int(v) if float(v) == int(v) else v
            line = f"click {fmt(x)},{fmt(y)}"
            if a.get("right"):
                line += " right"
            if a.get("double"):
                line += " double"
        elif op == "open":
            line = f"open {_q(a['name'])}"
        elif op == "url":
            line = f"url {_q(a['url'])}"
        elif op == "script":
            line = f"script {a['lang']} \"\"\"{a['code']}\"\"\""
        elif op == "wait":
            line = f"wait {a['ms']}"
        elif op in ("ask", "confirm", "done", "refuse"):
            key = {"ask": "question", "confirm": "summary",
                   "done": "summary", "refuse": "reason"}[op]
            line = f"{op} {_q(a[key])}"
        else:
            raise DSLError(f"cannot serialize op {op!r}", 0)
        lines.append(line)
        if a.get("expect"):
            lines.append("expect " + a["expect"])
    return "\n".join(lines)
