"""Small deterministic argument recoveries for common spoken phrasing."""

import re


_UP = re.compile(
    r"\b(?:up|louder|raise|increase|higher|brighter|brighten)\b",
    re.IGNORECASE)
_DOWN = re.compile(
    r"\b(?:down|quieter|softer|lower|decrease|dimmer|dim|darker)\b",
    re.IGNORECASE)
_SMALL = re.compile(r"\b(?:a little|a bit|slightly|a touch|a notch)\b",
                    re.IGNORECASE)
_LARGE = re.compile(r"\b(?:a lot|way|much|really|a ton)\b", re.IGNORECASE)


def vague_delta(text: str) -> int | None:
    up, down = bool(_UP.search(text)), bool(_DOWN.search(text))
    if up == down:
        return None
    magnitude = 30 if _LARGE.search(text) else 10
    return magnitude if up else -magnitude


def _normalized(text: str) -> str:
    text = text.lower().replace("’", "'")
    return " ".join(re.sub(r"[^a-z0-9\s']", " ", text).split())


def _hits(text: str, patterns: list[tuple[str, bool]]) -> list[tuple[int, int, bool]]:
    hits = []
    for pattern, value in patterns:
        hits.extend((m.start(), m.end(), value)
                    for m in re.finditer(pattern, text))
    kept = []
    for index, hit in enumerate(hits):
        start, end, _ = hit
        length = end - start
        if any(
                start < other_end and other_start < end
                and (other_end - other_start > length
                     or (other_end - other_start == length
                         and (other_start < start
                              or (other_start == start
                                  and other_index < index))))
                for other_index, (other_start, other_end, _) in
                enumerate(hits)):
            continue
        kept.append(hit)
    return kept


def _negated(text: str, start: int) -> bool:
    before = text[:start].split()[-3:]
    return any(token in {"don't", "dont", "never", "not"}
               for token in before) or \
        any(" ".join(before[i:i + 2]) == "do not"
            for i in range(max(0, len(before) - 1), len(before)))


_SOUND = r"(?:sound|audio|volume|speakers?)"
_MUTE = [
    (r"\b(?:mute|silence|hush)\b", True),
    (r"\bquiet\s+the\s+sound\b", True),
    (rf"\b{_SOUND}\b(?:\s+\w+){{0,4}}\s+\boff\b", True),
    (rf"\b(?:kill|cut|shut\s+off|turn\s+off)\b"
     rf"(?:\s+\w+){{0,4}}\s+\b{_SOUND}\b", True),
    (r"\bunmute\b", False),
    (rf"\b{_SOUND}\b(?:\s+\w+){{0,3}}\s+\b(?:back\s+)?on\b", False),
    (r"\bturn\s+(?:the\s+)?(?:sound|audio)\s+(?:back\s+)?on\b", False),
]
_DARK_MODE = [
    (r"\b(?:dark\s+(?:mode|theme)|night\s+mode|go\s+dark)\b", True),
    (r"\b(?:light\s+(?:mode|theme)|go\s+light)\b", False),
    (r"\bturn\s+off\s+(?:the\s+)?dark\b", False),
    (r"\bdisable\s+(?:the\s+)?dark\b", False),
    (r"\bdark\s+(?:mode|theme)\s+off\b", False),
]
_NETWORK = [
    (r"\boff\s+and\s+(?:then\s+)?back\s+on\b", True),
    (r"\boff\s+and\s+(?:then\s+)?on\b", True),
    (r"\bback\s+on\b", True),
    (r"\bturn\s+on\b", True),
    (r"\benable\b", True),
    (r"\bconnect\b", True),
    (r"\bon\b(?!\s+(?:my|the|this|that|your|it)\b)", True),
    (r"\bturn\s+off\b", False),
    (r"\bdisable\b", False),
    (r"\bdisconnect\b", False),
    (r"\boff\b", False),
]


def polarity(skill: str, text: str) -> bool | None | str:
    """Return the spoken on/off polarity, or ``negated`` for negated intent."""
    normalized = _normalized(text)
    if skill == "mute":
        patterns = _MUTE
    elif skill == "dark_mode":
        patterns = _DARK_MODE
    elif skill in ("wifi", "bluetooth"):
        patterns = _NETWORK
    else:
        return None
    hits = _hits(normalized, patterns)
    if any(_negated(normalized, start) for start, _, _ in hits):
        return "negated"
    values = {value for _, _, value in hits}
    return values.pop() if len(values) == 1 else None


def finder_view(text: str) -> str | None:
    patterns = (
        (r"\b(?:as\s+a\s+list|list\s+view)\b", "list"),
        (r"\b(?:as\s+icons?|icon\s+view)\b", "icons"),
        (r"\bcolumns?\s+view\b|\bcolumns?\b", "columns"),
        (r"\bgallery\b", "gallery"),
    )
    for pattern, view in patterns:
        if re.search(pattern, text, re.IGNORECASE):
            return view
    return None


def recover_duration(value, utterance: str) -> int | None | str:
    """Recover seconds from a model's unitless number using the utterance."""
    from . import decision
    from . import calc

    parsed = decision.parse_duration(str(value))
    if parsed is not None:
        return parsed
    normalized = calc.normalize(str(value))[0]
    if not re.fullmatch(r"\d+(?:\.\d+)?", normalized):
        return None
    parsed = decision.parse_duration(utterance)
    return parsed if parsed is not None else "ask"


_SPOKEN_NUMBERS = {
    0: "zero", 1: "one", 2: "two", 3: "three", 4: "four", 5: "five",
    6: "six", 7: "seven", 8: "eight", 9: "nine", 10: "ten",
    11: "eleven", 12: "twelve", 13: "thirteen", 14: "fourteen",
    15: "fifteen", 16: "sixteen", 17: "seventeen", 18: "eighteen",
    19: "nineteen", 20: "twenty", 30: "thirty", 40: "forty",
    50: "fifty", 60: "sixty", 70: "seventy", 80: "eighty",
    90: "ninety",
}


def duration_prompt_number(value, utterance: str) -> str:
    from . import calc

    normalized = calc.normalize(utterance)[0]
    numbers = re.findall(r"\b\d+(?:\.\d+)?\b", normalized)
    number = numbers[-1] if numbers else calc.normalize(str(value))[0]
    try:
        number = _SPOKEN_NUMBERS.get(int(float(number)), number)
    except ValueError:
        pass
    return number[:1].upper() + number[1:]
