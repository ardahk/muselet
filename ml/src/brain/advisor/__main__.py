"""CLI: python -m brain.advisor prep --household DIR [--format json|markdown|html]
        python -m brain.advisor script numbers-highlight|numbers-review|notes-brief --household DIR"""

from __future__ import annotations

import argparse
import json
import sys

from . import brief_html, brief_markdown, load_household, prep
from .scripts import notes_brief_script, numbers_highlight_script, numbers_review_script

SCRIPTS = {"numbers-highlight": numbers_highlight_script, "numbers-review": numbers_review_script,
           "notes-brief": notes_brief_script}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m brain.advisor")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("prep", help="compute the meeting prep (JSON with evidence + brief markdown)")
    p.add_argument("--household", required=True)
    p.add_argument("--format", choices=("json", "markdown", "html"), default="json")
    p.add_argument("--phrasing", help="JSON object of short number-free sentences (headline, lake_house, ...)")
    s = sub.add_parser("script", help="print an AppleScript for the app to run")
    s.add_argument("name", choices=sorted(SCRIPTS))
    s.add_argument("--household", required=True)
    s.add_argument("--phrasing")
    a = ap.parse_args(argv)

    result = prep(load_household(a.household))
    phrasing = json.loads(a.phrasing) if a.phrasing else None
    if a.cmd == "script":
        fn = SCRIPTS[a.name]
        sys.stdout.write(fn(result, phrasing) if a.name == "notes-brief" else fn(result))
        return 0
    md = brief_markdown(result, phrasing)
    if a.format == "markdown":
        sys.stdout.write(md)
    elif a.format == "html":
        sys.stdout.write(brief_html(md) + "\n")
    else:
        json.dump({"prep": result, "brief_markdown": md}, sys.stdout, indent=2, ensure_ascii=False)
        sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
