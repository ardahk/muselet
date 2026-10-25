"""Apply HandsKit act diffs to an observation text (AGENTS.md formats).

    + #31 button "Export"      element appeared (full Serializer line)
    - #7                       element gone
    ~ #4 value="hel" selected  element changed (value / checked|unchecked /
                               selected|unselected / enabled|disabled / moved)

The header line (`app: ... | window: "..." | focused: #4`) is kept; a diff
line starting with `app:` replaces it, and a removed focused ref is dropped
from it. Mirrors Serializer.line so the result matches a fresh observe.
"""

import re

_TEXT_ROLES = {"textfield", "textarea", "combobox"}
_VALUE_ROLES = {"slider", "stepper", "incrementor", "picker"}
_QSTR = r'"(?:[^"\\]|\\.)*"'
_LINE = re.compile(rf'^#(\d+)\s+(\S+)\s+({_QSTR})(.*)$')
_VALUE = re.compile(rf'value=({_QSTR})')


def _unesc(q: str) -> str:
    return re.sub(r"\\(.)", lambda m: {"n": "\n"}.get(m.group(1), m.group(1)),
                  q[1:-1])


def parse_line(line: str) -> dict | None:
    """'#4 textfield "Search" value="" selected' -> element dict."""
    m = _LINE.match(line.strip())
    if not m:
        return None
    rest = m.group(4)
    e = {"ref": int(m.group(1)), "role": m.group(2),
         "label": _unesc(m.group(3)), "enabled": " disabled" not in f" {rest}"}
    v = _VALUE.search(rest)
    if v:
        e["value"] = v.group(1)          # kept quoted/escaped verbatim
    flags = _VALUE.sub("", rest).split()
    if "checked" in flags:
        e["checked"] = True
    elif "unchecked" in flags:
        e["checked"] = False
    e["selected"] = "selected" in flags
    return e


def render_line(e: dict) -> str:
    s = f'#{e["ref"]} {e["role"]} "' + e["label"].replace("\\", "\\\\") \
        .replace('"', '\\"').replace("\n", "\\n") + '"'
    if "value" in e:
        if e["role"] in _TEXT_ROLES:
            s += f" value={e['value']}"
        elif (e["role"] in _VALUE_ROLES or
              (e["role"] == "button" and
               ("HotText" in e["label"] or e["label"] == "clipSpeed"))) \
                and _unesc(e["value"]):
            s += f" value={e['value']}"
    if "checked" in e:
        s += " checked" if e["checked"] else " unchecked"
    if e.get("selected"):
        s += " selected"
    if not e.get("enabled", True):
        s += " disabled"
    return s


def _change(e: dict, spec: str) -> None:
    v = _VALUE.search(spec)
    if v:
        e["value"] = v.group(1)
    for tok in _VALUE.sub("", spec).split():
        if tok in ("checked", "unchecked"):
            e["checked"] = tok == "checked"
        elif tok in ("selected", "unselected"):
            e["selected"] = tok == "selected"
        elif tok in ("enabled", "disabled"):
            e["enabled"] = tok == "enabled"


def apply_diff(obs_text: str, diff_text: str) -> str:
    """Return the observation text after applying `diff_text`."""
    lines = obs_text.split("\n") if obs_text else []
    header = lines[0] if lines and not lines[0].startswith("#") else ""
    body = lines[1:] if header else lines
    order: list[int] = []
    els: dict[int, dict | str] = {}       # ref -> element (or raw line)
    extra: list[str] = []                 # unparseable body lines, kept
    removed: set[int] = set()
    for ln in body:
        e = parse_line(ln)
        if e is None:
            if ln.strip():
                extra.append(ln)
            continue
        if e["ref"] not in els:
            order.append(e["ref"])
        els[e["ref"]] = e
    for d in (diff_text or "").split("\n"):
        d = d.strip()
        if d.startswith("app:"):
            header = d
        elif d.startswith("+ "):
            e = parse_line(d[2:])
            if e is not None:
                if e["ref"] not in els:
                    order.append(e["ref"])
                els[e["ref"]] = e
        elif d.startswith("- "):
            m = re.match(r"#(\d+)", d[2:].strip())
            if m and int(m.group(1)) in els:
                removed.add(int(m.group(1)))
                del els[int(m.group(1))]
                order.remove(int(m.group(1)))
        elif d.startswith("~ "):
            m = re.match(r"#(\d+)\s*(.*)$", d[2:].strip())
            if m and int(m.group(1)) in els:
                _change(els[int(m.group(1))], m.group(2))
    fm = re.search(r"\s*\|\s*focused: #(\d+)", header)
    if fm and int(fm.group(1)) in removed:
        header = header[:fm.start()] + header[fm.end():]
    out = ([header] if header else []) + extra + [render_line(els[r]) for r in order]
    return "\n".join(out)


def elements(obs_text: str, prev: list[dict] | None = None) -> list[dict]:
    """Element dicts from an observation text; frames carried over from
    `prev` for refs that persist (new elements have no frame)."""
    frames = {e.get("ref"): e.get("frame") for e in prev or [] if e.get("frame")}
    out = []
    for ln in obs_text.split("\n"):
        e = parse_line(ln)
        if e is None:
            continue
        if "value" in e:
            e["value"] = _unesc(e["value"])
        if e["ref"] in frames:
            e["frame"] = frames[e["ref"]]
        out.append(e)
    return out
