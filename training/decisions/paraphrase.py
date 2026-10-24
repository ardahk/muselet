from __future__ import annotations

import re
from collections import Counter

from .families.core import NAMES

PARAPHRASE_PROMPT = """Rewrite the following text so it reads naturally, as a real {doc_kind} would. Keep every number, date, time, name, identifier and
condition exactly as written (copy them verbatim). Do not add or remove facts. Return only the rewritten text."""

_NUMBER_OR_ID = re.compile(
    r"(?<![A-Za-z0-9_])(?:"
    r"[A-Z]{1,8}[-_]\d[A-Z0-9_-]*"
    r"|\d{4}-\d{2}-\d{2}(?:T\d{2}:\d{2}(?::\d{2})?(?:[-+]\d{2}:\d{2})?)?"
    r"|\d{1,2}:\d{2}(?::\d{2})?(?:\s?[AP]M)?"
    r"|[$€£]\s?\d+(?:,\d{3})*(?:\.\d+)?"
    r"|\d+(?:,\d{3})*(?:\.\d+)?%?"
    r")(?![A-Za-z0-9_])"
)
_NUMBER_WORD = re.compile(
    r"\b(?:zero|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|"
    r"thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty|"
    r"first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth)\b",
    re.IGNORECASE,
)
_UPPERCASE_ID = re.compile(r"\b[A-Z][A-Z0-9]{1,}\b")
_CONDITION = re.compile(
    r"\b(?:at least|at most|no more than|not more than|less than|greater than|"
    r"on or before|on or after|strictly above|strictly below|only if|only when|"
    r"unless|except|inclusive|exclusive|active|suspended|north|south|"
    r"true|false|must|may not|does not|cannot)\b",
    re.IGNORECASE,
)


def preservation_signature(text: str) -> Counter:
    markers = [
        *(("numeric_or_identifier", match.group(0)) for match in _NUMBER_OR_ID.finditer(text)),
        *(("number_word", match.group(0)) for match in _NUMBER_WORD.finditer(text)),
        *(("acronym", match.group(0)) for match in _UPPERCASE_ID.finditer(text)),
        *(("condition", match.group(0)) for match in _CONDITION.finditer(text)),
    ]
    for name in NAMES:
        markers.extend(("name", name) for _ in range(text.count(name)))
    return Counter(markers)


def validate_paraphrase(original: str, paraphrased: str) -> bool:
    return bool(paraphrased.strip()) and preservation_signature(original) == preservation_signature(paraphrased)
