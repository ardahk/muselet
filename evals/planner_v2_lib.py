"""Helpers for the v2 planner benchmark: observation builder that follows HandsKit's real serializer.

Rules taken from app/Sources/HandsKit/Observe.swift (Walker + Serializer), so the text matches `observe`:
  - roles are the kRoleMap short names only (button, textfield, textarea, checkbox, radio, popup, link, slider,
    menuitem, row, cell, text, combobox, image, tab); containers (group, table, outline, web area, toolbar)
    are never emitted, and search fields are plain `textfield` (AXTextField).
  - `value="..."` only on textfield / textarea / combobox; `checked`/`unchecked` only on checkbox / radio
    (System Settings switches are AXCheckBox); then `selected`, then `disabled`.
  - text / image lines exist only when labeled; a static text label is its value capped at 80 chars.
  - interactive records come first, then labeled text/images (Walker: `interactive + labeled`), refs are minted
    in that order from a process-wide counter (so a fresh window rarely starts at #1).
  - the header has ` | focused: #n` only when something is focused (no "focused: none").
  - window chrome without a title/description falls back to AXRoleDescription ("close button").
  - canvas apps (Premiere) get the orchestrator's BLIND_HINT line appended.
"""

import re

ROLES_INTERACTIVE = ("button", "textfield", "textarea", "checkbox", "radio", "popup", "link", "slider",
                     "menuitem", "row", "cell", "combobox", "tab")
ROLES_LABELED = ("text", "image")
VALUE_ROLES = ("textfield", "textarea", "combobox")
CHECK_ROLES = ("checkbox", "radio")
BLIND_HINT = 'Accessibility tree is empty here: use click "<description>"'
CHROME = ['button "close button"', 'button "minimize button"', 'button "full screen button"']
PROSE = [r"^(The|I |I'|Let|First|Now|Next|Since|This|To |Okay|Sure)", r"</?think>", r"^```"]

_ITEM = re.compile(r'^(?P<role>[a-z]+) "(?P<label>(?:[^"\\]|\\.)*)"(?P<rest>.*)$')


def esc(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def parse_item(s: str):
    m = _ITEM.match(s.strip())
    if not m:
        raise ValueError(f"bad item {s!r}")
    return m["role"], re.sub(r"\\(.)", r"\1", m["label"]), m["rest"].strip()


class Screen:
    """One observation. items: 'role "label" [value="..."] [checked|unchecked] [selected] [disabled]'."""

    def __init__(self, app, window, items, start=1, focus=None, blind=False, _refs=None, _next=None):
        self.app, self.window, self.blind = app, window, blind
        recs = [(r, l[:80] if r == "text" else l, x) for r, l, x in map(parse_item, items)]  # Observe.swift prefix(80)
        inter = [r for r in recs if r[0] not in ROLES_LABELED]
        lab = [r for r in recs if r[0] in ROLES_LABELED]
        self.recs, n = [], start
        for role, label, rest in inter + lab:
            key = (role, label)
            if _refs and key in _refs:
                ref = _refs[key]
            else:
                ref = n if _refs is None else _next
                if _refs is None:
                    n += 1
                else:
                    _next += 1
            self.recs.append([ref, role, label, rest])
        self.next = (n if _refs is None else _next)
        self.focus = focus
        if focus is not None:
            self.ref(focus)

    # ---- lookup ----
    def _find(self, key):
        hits = [r for r in self.recs if r[2] == key or f'{r[1]} "{r[2]}"' == key]
        if not hits and " " in key and '"' in key:
            role, label, _ = parse_item(key)
            hits = [r for r in self.recs if (r[1], r[2]) == (role, label)]
        if len(hits) != 1:
            raise KeyError(f"{key!r}: {len(hits)} matches in {self.window}")
        return hits[0]

    def ref(self, key) -> int:
        return self._find(key)[0]

    def r(self, key) -> str:
        return f"#{self.ref(key)}"

    def rx(self, key) -> str:
        """regex fragment for the ref, word-bounded"""
        return f"#{self.ref(key)}\\b"

    # ---- variants (refs of surviving elements stay stable, new ones are minted) ----
    def _items(self):
        return [f'{role} "{esc(label)}"' + (f" {rest}" if rest else "") for _, role, label, rest in self.recs]

    def _derive(self, items, window=None, focus="__same__", app=None):
        refs = {(r[1], r[2]): r[0] for r in self.recs}
        return Screen(app or self.app, window or self.window, items, focus=self.focus if focus == "__same__" else focus,
                      blind=self.blind, _refs=refs, _next=self.next)

    def set(self, key, new_item, **kw):
        old = self._find(key)
        items = [new_item if (r[0] == old[0]) else it for r, it in zip(self.recs, self._items())]
        role, label, _ = parse_item(new_item)
        refs = {(r[1], r[2]): r[0] for r in self.recs}
        refs[(role, label)] = old[0]
        s = Screen(kw.get("app") or self.app, kw.get("window") or self.window, items,
                   focus=kw.get("focus", self.focus), blind=self.blind, _refs=refs, _next=self.next)
        return s

    def add(self, *items, **kw):
        return self._derive(self._items() + list(items), kw.get("window"), kw.get("focus", "__same__"), kw.get("app"))

    def drop(self, *keys, **kw):
        gone = {self._find(k)[0] for k in keys}
        items = [it for r, it in zip(self.recs, self._items()) if r[0] not in gone]
        return self._derive(items, kw.get("window"), kw.get("focus", "__same__"), kw.get("app"))

    def with_(self, **kw):
        return self._derive(self._items(), kw.get("window"), kw.get("focus", "__same__"), kw.get("app"))

    @property
    def text(self) -> str:
        head = f'app: {self.app} | window: "{esc(self.window)}"'
        if self.focus is not None:
            head += f" | focused: #{self.ref(self.focus)}"
        lines = [head] + [f'#{ref} {role} "{esc(label)}"' + (f" {rest}" if rest else "")
                          for ref, role, label, rest in self.recs]
        if self.blind:
            lines.append(BLIND_HINT)
        return "\n".join(lines)


def q(s: str) -> str:
    """regex-escape literal text"""
    return re.escape(s)


SCENARIOS = []


def sc(id, cat, goal, screen, last=None, accept=(), reject=(), confirm_before=(), script_output=None,
       gold=(), wrong=(), tags=()):
    """Same fields as evals/planner_offline.sc() plus category, gold and wrong replies (one string per reply,
    newline-separated lines). PROSE is appended to reject like the v1 scenarios."""
    obs = screen.text if isinstance(screen, Screen) else screen.strip("\n")
    SCENARIOS.append({
        "id": f"v2-{id}", "tags": [cat, *tags], "category": cat, "goal": goal, "observation": obs,
        "last_batch": list(last) if last else None, "script_output": script_output,
        "accept_first": list(accept), "reject_any": list(reject) + PROSE, "confirm_before": list(confirm_before),
        "gold": [reply_lines(g) for g in gold], "wrong": [reply_lines(w) for w in wrong]})


def reply_lines(text: str) -> list[str]:
    """Reply text -> planner lines as the bench Runner yields them (a script block is one multi-line element)."""
    out, block = [], None
    for ln in text.strip("\n").split("\n"):
        if block is not None:
            block.append(ln)
            if '"""' in ln:
                out.append("\n".join(block).strip())
                block = None
            continue
        ln = ln.strip()
        if not ln:
            continue
        if re.match(r"^script\b", ln) and ln.count('"""') % 2:
            block = [ln]
            continue
        out.append(ln)
    if block is not None:
        raise ValueError(f"unterminated script block in reply: {text!r}")
    return out
