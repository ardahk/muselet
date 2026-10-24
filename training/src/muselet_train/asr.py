"""Deterministic ASR-noise augmentation (SPEC 1.3), applied to 30% of items after labeling."""

from __future__ import annotations

import random
import re
import zlib

NUM = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven",
       "twelve", "thirteen", "fourteen", "fifteen", "sixteen", "seventeen", "eighteen", "nineteen", "twenty"]
TENS = {"thirty": 30, "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90}
W2D = {w: i for i, w in enumerate(NUM)} | TENS
D2W = {v: k for k, v in W2D.items()}
HOMO = {"to": ["two", "too"], "two": ["to"], "too": ["to"], "for": ["four"], "four": ["for"],
        "write": ["right"], "right": ["write"]}
FILLERS = ["um", "uh", "like"]
RATE = 0.30


def _rng(key: str) -> random.Random:
    return random.Random(zlib.crc32(key.encode()))


def selected(key: str) -> bool:
    return _rng("sel:" + key).random() < RATE


def _numbers(words: list[str], rng: random.Random) -> list[str]:
    out = []
    for w in words:
        if w.isdigit() and int(w) in D2W and rng.random() < 0.5:
            out.append(D2W[int(w)])
        elif w in W2D and rng.random() < 0.5:
            out.append(str(W2D[w]))
        else:
            out.append(w)
    return out


def noise(text: str, key: str) -> str:
    """One noisy variant of `text`; the same (text, key) always gives the same output."""
    rng = _rng("noise:" + key)
    t = text.lower()
    t = re.sub(r"[^\w\s'-]", " ", t)
    t = re.sub(r"(?<!\w)-|-(?!\w)", " ", t)
    w = t.split()
    if not w:
        return text
    if w[0] in ("hey", "please") and len(w) > 1 and rng.random() < 0.7:
        w = w[1:]
    if len(w) > 2 and w[-1] == "please" and rng.random() < 0.5:
        w = w[:-1]
    w = _numbers(w, rng)
    w = [rng.choice(HOMO[x]) if x in HOMO and rng.random() < 0.3 else x for x in w]
    if rng.random() < 0.5:
        for _ in range(1 + (rng.random() < 0.3)):
            w.insert(rng.randrange(len(w) + 1), rng.choice(FILLERS))
    if len(w) >= 3 and rng.random() < 0.2:
        k = rng.randint(1, min(3, len(w) - 1))
        start = w[:k]
        start[-1] += "-"
        w = start + w
    return " ".join(w)
