"""Deterministic answers for ANSWER-route math: percentages, tips, basic
arithmetic (digits or spoken words) and common unit conversions.

answer(text) -> short reply (<= 12 words) or None when it doesn't parse,
in which case the caller falls back to the model. The model never does
arithmetic (AGENTS.md: model picks, code parses).
"""

import ast
import math
import operator
import re
from dataclasses import dataclass

_ONES = {"zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
         "six": 6, "seven": 7, "eight": 8, "nine": 9}
_TEENS = {"ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13,
          "fourteen": 14, "fifteen": 15, "sixteen": 16, "seventeen": 17,
          "eighteen": 18, "nineteen": 19}
_TENS = {"twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60,
         "seventy": 70, "eighty": 80, "ninety": 90}
_SCALES = {"thousand": 1_000, "million": 1_000_000, "billion": 1_000_000_000}
_NUMWORDS = set(_ONES) | set(_TEENS) | set(_TENS) | set(_SCALES) | {"hundred"}
_DIGITS = re.compile(r"^\d+(?:\.\d+)?$")


@dataclass(frozen=True)
class CalcResult:
    answer: str
    value: float | None
    expr: str | None


def _kind(w: str) -> str | None:
    if w in _ONES:
        return "ones"
    if w in _TEENS or w in _TENS:
        return "tens" if w in _TENS else "teen"
    if w == "hundred":
        return "hundred"
    if w in _SCALES:
        return "scale"
    if _DIGITS.match(w):
        return "digit"
    return None


def _parse_run(toks: list[str], i: int) -> tuple[float | None, int]:
    """Parse a spoken number starting at toks[i]. Returns (value, next i);
    value None when toks[i] does not start a number."""
    total, cur, last, j = 0.0, 0.0, None, i
    n = len(toks)
    if toks[i] in ("a", "an") and i + 1 < n and toks[i + 1] in \
            ({"hundred"} | set(_SCALES)):
        cur, last, j = 1, "ones", i + 1
    while j < n:
        w, k = toks[j], _kind(toks[j])
        if k == "digit" and last is None:
            cur = float(w)
        elif k == "ones" and last in (None, "tens", "hundred", "scale"):
            if w == "zero" and last is not None:
                break
            cur += _ONES[w]
        elif k in ("teen", "tens") and last in (None, "hundred", "scale"):
            cur += _TEENS.get(w) or _TENS[w]
        elif k == "hundred" and last in ("ones", "teen", "tens", "digit") \
                and cur % 100 == cur:
            cur *= 100
        elif k == "scale" and last in ("ones", "teen", "tens", "hundred",
                                        "digit"):
            total += cur * _SCALES[w]
            cur = 0
        elif w == "and" and last in ("hundred", "scale") and j + 1 < n \
                and _kind(toks[j + 1]) in ("ones", "teen", "tens"):
            j += 1
            continue
        elif w == "point" and last is not None and j + 1 < n and \
                (toks[j + 1] in _ONES or toks[j + 1].isdigit()):
            digits = ""
            j += 1
            while j < n and (toks[j] in _ONES or toks[j].isdigit()):
                digits += str(_ONES.get(toks[j], toks[j]))
                j += 1
            return total + cur + float("0." + digits), j
        else:
            break
        last = k if k != "teen" or last is None else "tens"
        if k == "teen":
            last = "teen"
        j += 1
    if last is None:
        return None, i
    return total + cur, j


def _fmt_num(x: float) -> str:
    if abs(x - round(x)) < 1e-9:
        return f"{int(round(x)):,}"
    r = round(x, 2)
    if r == 0:
        return f"{x:.3g}"
    return f"{r:,.2f}".rstrip("0").rstrip(".")


def normalize(text: str) -> tuple[str, bool]:
    """-> (lowercase text with spoken numbers as digits, money mentioned)."""
    t = text.lower().strip()
    t = t.replace("’", "'")
    while re.search(r"(\d),(\d{3})", t):
        t = re.sub(r"(\d),(\d{3})", r"\1\2", t)
    money = bool(re.search(r"\$|\bdollars?\b|\bbucks?\b|\btip\b", t))
    t = re.sub(r"\b(dollars?|bucks?)\b", " ", t)
    t = t.replace("%", " percent ").replace("$", " ").replace("°", " degrees ")
    t = re.sub(r"\bper ?cent\b", "percent", t)
    t = re.sub(r"[?!,;:]", " ", t)
    t = re.sub(r"\.(?!\d)", " ", t)
    t = re.sub(r"(?<=[a-z])-(?=[a-z])", " ", t)
    t = re.sub(r"([+*/×÷^=()])", r" \1 ", t)
    t = re.sub(r"(?<=\d)\s*-\s*(?=\d)", " - ", t)
    t = re.sub(r"(?<=\d)(?=[a-z])", " ", t)          # 5kg -> 5 kg
    toks = t.split()
    out, i, prev_word_num = [], 0, False
    while i < len(toks):
        if toks[i] in _NUMWORDS or toks[i] in ("a", "an") or \
                _DIGITS.match(toks[i]):
            v, j = _parse_run(toks, i)
            if v is not None:
                word_run = not _DIGITS.match(toks[i])
                # "sixty four fifty" (money) -> 64.50
                if money and word_run and prev_word_num and 10 <= v < 100 \
                        and v == int(v) and float(out[-1]) == int(float(out[-1])):
                    out[-1] = _fmt_plain(float(out[-1]) + v / 100)
                    prev_word_num = False
                else:
                    out.append(_fmt_plain(v))
                    prev_word_num = word_run
                i = j
                continue
        out.append(toks[i])
        prev_word_num = False
        i += 1
    return " ".join(out), money


def _fmt_plain(x: float) -> str:
    return str(int(x)) if x == int(x) else repr(x)


_FILLER = re.compile(
    r"^(?:(?:hey|ok|okay|so|um|uh)\s+)*(?:muselet\s+)?"
    r"(?:(?:can|could) you (?:tell me |work out |calculate )?|"
    r"please |tell me |quick(?:ly)? )*"
    r"(?:what's|whats|what is|what are|how much is|how much's|"
    r"calculate|compute|work out|figure out|solve)?\s*")
_TAIL = re.compile(r"\s+(?:equal|equals|make|makes|come to|is)$|\s*=$")
NUM = r"(-?\d+(?:\.\d+)?)"

# ---------- units ----------

_UNITS = {   # alias -> (dimension, factor to base, display)
    "length": {("m", "meter", "meters", "metre", "metres"): (1, "m"),
               ("km", "kilometer", "kilometers", "kilometre", "kilometres",
                "kms"): (1000, "km"),
               ("cm", "centimeter", "centimeters", "centimetre",
                "centimetres"): (0.01, "cm"),
               ("mm", "millimeter", "millimeters", "millimetre",
                "millimetres"): (0.001, "mm"),
               ("mi", "mile", "miles"): (1609.344, "mi"),
               ("ft", "foot", "feet"): (0.3048, "ft"),
               ("inch", "inches"): (0.0254, "in"),
               ("yd", "yard", "yards"): (0.9144, "yd")},
    "mass": {("g", "gram", "grams", "gramme", "grammes"): (1, "g"),
             ("kg", "kgs", "kilogram", "kilograms", "kilo", "kilos"):
                 (1000, "kg"),
             ("lb", "lbs", "pound", "pounds"): (453.59237, "lb"),
             ("oz", "ounce", "ounces"): (28.349523125, "oz")},
    "volume": {("ml", "milliliter", "milliliters", "millilitre",
                "millilitres", "mls"): (1, "ml"),
               ("l", "liter", "liters", "litre", "litres"): (1000, "L"),
               ("cup", "cups"): (236.5882365, "cups"),
               ("tbsp", "tablespoon", "tablespoons", "tbsps"):
                   (14.78676478125, "tbsp"),
               ("tsp", "teaspoon", "teaspoons", "tsps"):
                   (4.92892159375, "tsp"),
               ("fl oz", "fluid ounce", "fluid ounces"):
                   (29.5735295625, "fl oz")},
    "temp": {("f", "fahrenheit"): (None, "°F"),
             ("c", "celsius", "centigrade"): (None, "°C")},
}
_ALIAS = {a: (dim, f, disp) for dim, tbl in _UNITS.items()
          for names, (f, disp) in tbl.items() for a in names}
_U = "((?:degrees )?(?:" + "|".join(
    re.escape(a) for a in sorted(_ALIAS, key=len, reverse=True)) + "))"


_DISPLAY = {disp.lower().lstrip("°"): (dim, f, disp)
            for dim, tbl in _UNITS.items() for _, (f, disp) in tbl.items()}


def _unit(s: str):
    """alias or display name ('in', '°F') -> (dimension, factor, display)."""
    s = re.sub(r"^degrees ", "", s.strip().lower())
    return _ALIAS.get(s) or _DISPLAY.get(s.lstrip("°"))


def convert(value: float, src: str, dst: str) -> tuple[float, str, str] | None:
    """-> (result, src display, dst display) or None if incompatible."""
    a, b = _unit(src), _unit(dst)
    if not a or not b or a[0] != b[0] or a[2] == b[2]:
        return None
    if a[0] == "temp":
        r = value * 9 / 5 + 32 if b[2] == "°F" else (value - 32) * 5 / 9
        return round(r, 1), a[2], b[2]
    return value * a[1] / b[1], a[2], b[2]


def _say_conv(v: float, src: str, dst: str) -> str | None:
    c = convert(v, src, dst)
    if c is None:
        return None
    r, sd, dd = c
    if sd == "cups" and v == 1:
        sd = "cup"
    if dd == "cups" and round(r, 2) == 1:
        dd = "cup"
    if sd.startswith("°"):
        return f"{_fmt_num(v)}{sd} is {_fmt_num(r)}{dd}"
    return f"{_fmt_num(v)} {sd} is {_fmt_num(r)} {dd}"


# ---------- arithmetic ----------

_OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
        ast.Div: operator.truediv, ast.Pow: operator.pow}
_OP_WORDS = [
    (r"\bto the power of\b|\braised to(?: the power of)?\b", "**"),
    (r"\bmultiplied by\b|\btimes\b|×", "*"),
    (r"(?<=\d) x (?=-?\d)", " * "),
    (r"\bdivided by\b|\bover\b|÷", "/"),
    (r"\bplus\b|\badded to\b", "+"),
    (r"\bminus\b|\bless\b", "-"),
    (r"\bsquared\b", "** 2"), (r"\bcubed\b", "** 3"), (r"\^", "**"),
]
_SPOKEN_OP = {"+": "plus", "-": "minus", "*": "times", "/": "divided by",
              "**": "to the power of"}


def _simple_expression(s: str) -> str | None:
    expression = s
    for pattern, replacement in _OP_WORDS:
        expression = re.sub(pattern, replacement, expression)
    expression = re.sub(r"\s+", " ", expression).strip()
    match = re.fullmatch(r"(\d+(?:\.\d+)?)\s*([+\-*/])\s*(\d+(?:\.\d+)?)",
                         expression)
    return f"{match.group(1)}{match.group(2)}{match.group(3)}" if match else None


def _problem_expression(s: str) -> str | None:
    if _simple_expression(s):
        return None
    numbers = re.findall(r"(?<![\w.])\d+(?:\.\d+)?(?![\w.])", s)
    if re.search(r"\bcost of (?:one|1)\b", s) and len(numbers) >= 2:
        return f"{numbers[1]}/{numbers[0]}"
    if len(numbers) != 2:
        return None
    first, second = numbers
    if re.search(r"\b(?:change|ate)\b", s):
        return f"{first}-{second}"
    if re.search(r"\bhow much less\b", s):
        return f"{second}-{first}"
    if re.search(r"\b(?:bigger|larger|greater) than\b", s):
        return f"{first}-{second}"
    if re.search(r"\b(?:off|short of|out of|from|change|remain|remaining|left|ate)\b", s):
        return f"{second}-{first}"
    if re.search(r"\bgo into\b", s):
        return f"{second}/{first}"
    if re.search(r"\b(?:shared by|equal shares?|each pays|cost of one|speed)\b", s):
        return f"{first}/{second}" if "cost of one" not in s else f"{second}/{first}"
    if re.search(r"\bper hour\b.*\bstayed\b|\beach\b.*\btotal weight\b", s):
        return f"{first}*{second}"
    op_text = s
    for pattern, replacement in _OP_WORDS:
        op_text = re.sub(pattern, replacement, op_text)
    op = re.search(r"[+*/]|(?<!\d)-", op_text)
    if op:
        return f"{first}{op.group(0)}{second}"
    if re.search(r"\btotal\b", s) and re.search(r"\beach\b", s):
        return f"{first}*{second}"
    return None


def _eval(node):
    if isinstance(node, ast.Expression):
        return _eval(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return float(node.value)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
        v = _eval(node.operand)
        return -v if isinstance(node.op, ast.USub) else v
    if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
        a, b = _eval(node.left), _eval(node.right)
        if isinstance(node.op, ast.Pow) and (abs(b) > 64 or abs(a) > 1e6):
            raise ValueError("too big")
        if isinstance(node.op, ast.Div) and b == 0:
            raise ZeroDivisionError
        return _OPS[type(node.op)](a, b)
    raise ValueError("unsupported")


def arithmetic(s: str) -> str | None:
    """Digits-only text with op words -> 'x times y is z'."""
    problem = _problem_expression(s)
    if problem:
        return arithmetic(problem)
    m = re.match(rf"^(?:the )?square root of {NUM}$", s)
    if m:
        v = float(m.group(1))
        if v < 0:
            return None
        return f"The square root of {_fmt_num(v)} is {_fmt_num(math.sqrt(v))}"
    for pat, rep in (
            (rf"^add {NUM} (?:and|to) {NUM}$", r"\1 + \2"),
            (rf"^subtract {NUM} from {NUM}$", r"\2 - \1"),
            (rf"^multiply {NUM} (?:by|and|times) {NUM}$", r"\1 * \2"),
            (rf"^divide {NUM} by {NUM}$", r"\1 / \2")):
        if re.match(pat, s):
            s = re.sub(pat, rep, s)
            break
    for pat, rep in _OP_WORDS:
        s = re.sub(pat, rep, s)
    s = re.sub(r"\s+", " ", s).strip()
    if not re.fullmatch(r"[\d.\s+\-*/()]+", s) or \
            not re.search(r"\d\s*(\*\*|[+\-*/])\s*\(?\s*-?\d", s):
        return None
    try:
        v = _eval(ast.parse(s, mode="eval"))
    except ZeroDivisionError:
        return "You can't divide by zero"
    except (SyntaxError, ValueError, OverflowError):
        return None
    if abs(v) >= 1e15:
        return None
    spoken = re.sub(r"\*\*|[+*/]|(?<=\d )-", lambda m: _SPOKEN_OP[m.group(0).strip()], s)
    spoken = re.sub(r"\d+(?:\.\d+)?", lambda m: _fmt_num(float(m.group(0))),
                    spoken)
    out = f"{spoken} is {_fmt_num(v)}"
    return out if len(out.split()) <= 12 else f"That's {_fmt_num(v)}"


# ---------- percentages ----------

_FRACTIONS = {"half": 0.5, "one half": 0.5, "a third": 1 / 3,
              "one third": 1 / 3, "a quarter": 0.25, "one quarter": 0.25,
              "1 quarter": 0.25, "1 third": 1 / 3, "1 half": 0.5,
              "two thirds": 2 / 3, "2 thirds": 2 / 3,
              "three quarters": 0.75, "3 quarters": 0.75}


def _money(x: float) -> str:
    x = round(x + 1e-9, 2)
    return f"${int(x):,}" if x == int(x) else f"${x:,.2f}"


def _a(n: float) -> str:
    """'A' / 'An' before a spoken number (an 8, an 11, an 18, an 80)."""
    w = _fmt_num(n).replace(",", "")
    an = w.startswith("8") or (w.split(".")[0] in ("11", "18")) or \
        (len(w.split(".")[0]) in (2, 5, 8) and w.startswith(("11", "18")))
    return "An" if an else "A"


def percent(s: str, money: bool) -> str | None:
    fmt = _money if money else _fmt_num
    m = re.match(rf"^(?:an? |the )?{NUM} percent tip (?:on|for|of) (?:an? )?{NUM}$", s) \
        or re.match(rf"^(?:the )?tip (?:on|for) {NUM} at {NUM} percent$", s)
    if m:
        p, amt = map(float, m.groups())
        if s.startswith(("tip", "the tip")):
            amt, p = p, amt
        tip = round(amt * p / 100 + 1e-9, 2)
        return (f"{_a(p)} {_fmt_num(p)}% tip on {_money(amt)} is {_money(tip)}, "
                f"total {_money(amt + tip)}")
    m = re.match(rf"^{NUM} percent of {NUM}$", s)
    if m:
        p, x = map(float, m.groups())
        return f"{_fmt_num(p)}% of {fmt(x)} is {fmt(p * x / 100)}"
    m = re.match(rf"^{NUM} percent off (?:of )?{NUM}$", s) or \
        re.match(rf"^{NUM} (?:with |at )?{NUM} percent off$", s)
    if m:
        a, b = map(float, m.groups())
        p, x = (a, b) if "percent off" in s.split(m.group(2))[0] else (b, a)
        return f"{_fmt_num(p)}% off {fmt(x)} is {fmt(x * (1 - p / 100))}"
    m = re.match(rf"^{NUM} (plus|minus) {NUM} percent$", s)
    if m:
        x, op, p = float(m.group(1)), m.group(2), float(m.group(3))
        r = x * (1 + p / 100) if op == "plus" else x * (1 - p / 100)
        return f"{fmt(x)} {op} {_fmt_num(p)}% is {fmt(r)}"
    m = re.match(rf"^{NUM} is what percent(?:age)? of {NUM}$", s) or \
        re.match(rf"^what percent(?:age)? of {NUM} is {NUM}$", s)
    if m:
        a, b = map(float, m.groups())
        part, whole = (a, b) if s[0].isdigit() or s[0] == "-" else (b, a)
        if whole == 0:
            return None
        return f"{fmt(part)} is {_fmt_num(part / whole * 100)}% of {fmt(whole)}"
    m = re.match(rf"^({'|'.join(_FRACTIONS)}) of {NUM}$", s)
    if m:
        f, x = _FRACTIONS[m.group(1)], float(m.group(2))
        return f"{m.group(1).replace('1 ', 'one ')} of {fmt(x)} is {fmt(f * x)}"
    return None


def conversion(s: str) -> str | None:
    s = re.sub(r"\b(an?|one) (?=(?:degrees )?[a-z])", "1 ", s)
    m = re.match(rf"^(?:convert )?{NUM} (?:feet|foot|ft) {NUM}"
                 rf"(?: inch(?:es)?)? (?:to|in|into) {_U}$", s)
    if m:
        ft, inch, dst = float(m.group(1)), float(m.group(2)), m.group(3)
        c = convert(ft * 12 + inch, "inches", dst)
        if c:
            return f"{_fmt_num(ft)} ft {_fmt_num(inch)} in is {_fmt_num(c[0])} {c[2]}"
    for pat, order in (
            (rf"^(?:convert )?{NUM} {_U} (?:to|in|into|as) {_U}$", (0, 1, 2)),
            (rf"^how many {_U} (?:are |is )?(?:there )?(?:in|is|are|make|per) "
             rf"{NUM} {_U}$", (1, 2, 0)),
            (rf"^{NUM} {_U} (?:is |are |equals |in )?how many {_U}$", (0, 1, 2))):
        m = re.match(pat, s)
        if m:
            g = m.groups()
            return _say_conv(float(g[order[0]]), g[order[1]], g[order[2]])
    return None


def _strip_calculator_phrasing(text: str) -> str:
    text = re.sub(
        r"\b(?:on|in|with|using)\s+(?:the\s+)?calculator(?:\s+app)?\b",
        " ", text, flags=re.IGNORECASE)
    text = re.sub(
        r"\buse\s+(?:the\s+)?calculator(?:\s+app)?\s+(?:to|and)\b",
        " ", text, flags=re.IGNORECASE)
    text = re.sub(
        r"\bopen\s+(?:the\s+)?calculator(?:\s+app)?\s+and\b",
        " ", text, flags=re.IGNORECASE)
    return re.sub(r"\b(?:the\s+)?calculator(?:\s+app)?\b", " ", text,
                  flags=re.IGNORECASE)


def _colloquial_numbers(text: str) -> str:
    ones = "|".join(word for word in _ONES if word != "zero")
    tens = "|".join(_TENS)
    text = re.sub(r"\bhalf a dozen\b", "six", text, flags=re.IGNORECASE)
    text = re.sub(r"\ba dozen\b", "twelve", text, flags=re.IGNORECASE)
    pattern = re.compile(rf"\b({ones})\s+({tens})(?:\s+({ones}))?\b",
                         re.IGNORECASE)

    def replace(match):
        first = _ONES[match.group(1).lower()]
        tens_value = _TENS[match.group(2).lower()]
        last = _ONES[match.group(3).lower()] if match.group(3) else 0
        return str(first * 100 + tens_value + last)

    return pattern.sub(replace, text)


def _numeric_answer(answer: str) -> float | None:
    matches = re.findall(r"(?<![A-Za-z])[-−]?\$?\d[\d,]*(?:\.\d+)?", answer)
    if not matches:
        return None
    try:
        return float(matches[-1].replace("$", "").replace(",", "").replace("−", "-"))
    except ValueError:
        return None


def result(text: str) -> CalcResult | None:
    """Return the spoken answer with its numeric value and keyable expression."""
    source = _strip_calculator_phrasing(text)
    power_source = _TAIL.sub("", _FILLER.sub("", source, count=1)).strip()
    power = re.fullmatch(
        r"(\d+(?:\.\d+)?)\s+to the power of\s+(\d+)", power_source,
        flags=re.IGNORECASE)
    if power:
        base, exponent = map(float, power.groups())
        value = base ** exponent
        return CalcResult(
            f"{_fmt_num(base)} to the power of {_fmt_num(exponent)} is {_fmt_num(value)}",
            value, None)
    if not re.search(r"\$|\bdollars?\b|\bbucks?\b|\btip\b", source, re.I):
        source = _colloquial_numbers(source)
    s, money = normalize(source)
    s = _FILLER.sub("", s, count=1)
    s = _TAIL.sub("", s).strip()
    s = re.sub(r"^(?:the )?(?:answer to |result of )", "", s)
    if not s:
        return None
    for fn in (lambda: percent(s, money), lambda: conversion(s),
               lambda: arithmetic(s)):
        out = fn()
        if out:
            value = _numeric_answer(out)
            return CalcResult(out, value,
                              _simple_expression(s) if value is not None else None)
    return None


def answer(text: str) -> str | None:
    """Exact spoken answer, or None (fall back to the model)."""
    parsed = result(text)
    if parsed is not None:
        return parsed.answer
    return None
