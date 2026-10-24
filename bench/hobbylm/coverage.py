"""Generate an explicit, per-request coverage map from frozen HobbyLM sets."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _tasks(upstream: Path):
    frozen = upstream / "data/frozen"
    r4 = []
    for line in (frozen / "hobbymac-sealed-test-r4.tsv").read_text().splitlines():
        if line.strip():
            ident, kind, text, expected = line.split("\t", 3)
            r4.append((f"hobbylm/sealed-r4", ident, kind, text, expected.strip()))
    settings = json.loads((frozen / "tasks.json").read_text())
    template = settings["goal_template"]
    for item in settings["dev"] + settings["held_out"]:
        r4.append(("hobbylm/system-settings", item["id"], "settings", template.format(dest=item["dest"]), item["dest"]))
    calc = json.loads((frozen / "calc-tasks.json").read_text())
    for index, (text, expected) in enumerate(calc["dev"], 1):
        r4.append(("hobbylm/calc-tasks/dev", f"D{index:02d}", "calc", text, str(expected)))
    index = 1
    for group, examples in calc["held_out"].items():
        for text, expected in examples:
            r4.append(("hobbylm/calc-tasks", f"{group}-{index:02d}", "calc", text, str(expected)))
            index += 1
    return r4


def _mapping(kind, text, expected):
    if kind == "calc":
        return "MULTI_STEP", "no", "No calculator/arithmetic skill; needs app flow and computed value."
    if kind == "settings":
        return "MULTI_STEP", "no", "No native System Settings navigation skill."
    if kind == "device":
        if expected.startswith("BRIGHTNESS_"):
            return "set_brightness", "no", "Skill requires an absolute level; request gives direction only."
        if expected == "MUTE":
            return "mute", "yes", ""
        return "change_volume", "yes", ""
    if kind == "dark":
        return "dark_mode", "yes", ""
    if kind == "app":
        return "open_app", "yes", ""
    if kind == "folder":
        return "open_folder", "yes", ""
    if kind == "timer":
        return "start_timer", "yes", "start_timer is declared in the catalog but not implemented in HandsKit."
    if kind == "screenshot":
        return "take_screenshot", "yes", ""
    if kind == "event":
        return "create_event", "no", "Skill has no invitee/attendee argument."
    return "REFUSE", "yes", ""


def build(upstream: Path, catalog_path: Path) -> str:
    catalog = json.loads(catalog_path.read_text())
    skills = {item["name"] for item in catalog["skills"]}
    rows = []
    gaps = Counter()
    for source, ident, kind, text, expected in _tasks(upstream):
        target, args, gap = _mapping(kind, text, expected)
        if target not in skills and target not in ("MULTI_STEP", "ASK", "REFUSE", "ANSWER"):
            raise ValueError(f"mapping references missing catalog skill {target!r}")
        rows.append((source, ident, kind, text, expected, target, args, gap))
        if gap:
            gaps[gap] += 1
    lines = [
        "# HobbyLM request coverage",
        "",
        "`coverage.py` maps every frozen r4 task, all 15 System Settings navigation requests, and all Calculator held-out requests.",
        "Mappings are explicit in `_mapping`; `args` says whether the catalog skill/flow can express the requested arguments.",
        "",
        "| Source | ID | Kind | Request | Expected | Skill / flow | Args expressible? | Gap |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for source, ident, kind, text, expected, target, args, gap in rows:
        cells = (source, ident, kind, text, expected, target, args, gap)
        lines.append("| " + " | ".join(str(value).replace("|", "\\|").replace("\n", " ") for value in cells) + " |")
    lines.extend(["", "## Ranked coverage gaps", "", "| Rank | Gap | Requests blocked |", "|---:|---|---:|"])
    for rank, (gap, count) in enumerate(gaps.most_common(10), 1):
        lines.append(f"| {rank} | {gap} | {count} |")
    return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--upstream", type=Path, default=Path(__file__).resolve().parent / "upstream")
    parser.add_argument("--catalog", type=Path, default=ROOT / "skills/catalog.json")
    parser.add_argument("--out", type=Path, default=Path(__file__).resolve().parent / "coverage.md")
    args = parser.parse_args(argv)
    args.out.write_text(build(args.upstream, args.catalog), encoding="utf-8")
    print(args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
