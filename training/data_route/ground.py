"""ARGS grounding: every value must appear in the utterance or follow from it by the documented coercions
(postprocess.norm_args: spoken numbers -> digits, max/full -> 100, half -> 50, change_volume a bit/a lot; bools and
enums from the words; canonical app names; well-known folders; bare site name -> its domain)."""

from __future__ import annotations

import re

from muselet_train.asr import W2D
from muselet_train.decontam import norm

APP_ALIAS = {"Premiere Pro": ["premiere"], "Google Chrome": ["chrome"], "Visual Studio Code": ["vs code", "vscode", "code"],
             "System Settings": ["settings", "system preferences"], "Microsoft Word": ["word"],
             "Microsoft Excel": ["excel"], "Microsoft PowerPoint": ["powerpoint"], "App Store": ["app store"],
             "Activity Monitor": ["activity monitor"], "FaceTime": ["facetime", "face time"]}
SITE_ALIAS = {"mail.google.com": ["gmail", "g mail", "google mail"], "docs.google.com": ["google docs", "docs"],
              "nytimes.com": ["new york times", "nyt", "ny times"], "drive.google.com": ["google drive", "drive"],
              "calendar.google.com": ["google calendar"], "maps.google.com": ["google maps"],
              "x.com": ["twitter", "x"], "news.ycombinator.com": ["hacker news", "hn"],
              "sheets.google.com": ["google sheets", "sheets"], "en.wikipedia.org": ["wikipedia"],
              "wsj.com": ["wall street journal", "wsj"], "bbc.com": ["bbc"], "bbc.co.uk": ["bbc"]}
STOP = {"the", "a", "an", "my", "to", "that", "and", "of", "for", "i", "it", "is", "in", "on", "me", "about", "please"}


UNIT = {"min": "minutes", "mins": "minutes", "minute": "minutes", "sec": "seconds", "secs": "seconds",
        "second": "seconds", "hr": "hours", "hrs": "hours", "hour": "hours"}


def _toks(s: str) -> list[str]:
    out = []
    for w in norm(s.replace("'", "")).split():
        w = UNIT.get(w, w)
        out.append(str(W2D[w]) if w in W2D else w)
    return out


def _covered(value: str, utt: str, min_frac: float = 1.0) -> bool:
    u = set(_toks(utt))
    v = [w for w in _toks(value) if w not in STOP] or _toks(value)
    if not v:
        return False
    return sum(w in u or w.rstrip("s") in u or w + "s" in u for w in v) / len(v) >= min_frac


def grounded(skill: str, args: dict, utt: str, spec: dict) -> str | None:
    """None if every value is grounded, else the reason."""
    un = " " + norm(utt) + " "
    for k, v in args.items():
        t = spec[k]["type"]
        if t in ("int", "bool", "enum"):
            continue  # norm_args already derived/validated them from the words
        s = str(v)
        if t == "app":
            if _covered(s, utt) or any(f" {a} " in un for a in APP_ALIAS.get(s, [])):
                continue
            return f"app:{s}"
        if t == "url":
            host = re.sub(r"^(https?://)?(www\.)?", "", s.lower()).split("/")[0]
            core = host.rsplit(".", 2)[-2] if host.count(".") >= 1 else host
            alias = SITE_ALIAS.get(host, [])
            if core in un.replace(" ", "") or any(f" {a} " in un for a in alias) or _covered(s.replace(".", " "), utt):
                continue
            return f"url:{s}"
        if t == "path":
            last = re.split(r"[/~]", s.strip("/"))[-1] or s
            if _covered(last, utt):
                continue
            return f"path:{s}"
        if skill == "compose_text" and k == "target":
            if s in ("notes", "document"):
                continue
            return f"target:{s}"
        if not _covered(s, utt):
            return f"{t}:{k}={s}"
    return None
