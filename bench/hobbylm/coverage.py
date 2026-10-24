"""Build a ranked coverage map from frozen HobbyLM and extension sets."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATASETS = ("r4", "r1", "r2", "r3", "calc", "settings")
GAP_EVIDENCE = {
    "Calculator/arithmetic has no executable skill or route": (
        "skills/catalog.json:4-8,10-113; ml/src/brain/orchestrator.py:143-165; "
        "app/Sources/HandsKit/Skills.swift:186-371",
    ),
    "Native System Settings navigation is not implemented": (
        "skills/catalog.json:4-8,10-113; ml/src/brain/orchestrator.py:143-165; "
        "app/Sources/HandsKit/Skills.swift:186-371",
    ),
    "Event requests with people cannot create invitees": (
        "skills/catalog.json:72-73; app/Sources/HandsKit/Skills.swift:571-584",
    ),
    "Countdown timers have no executable start_timer implementation": (
        "skills/catalog.json:69-70; app/Sources/HandsKit/Skills.swift:186-371",
    ),
    "Directional brightness has no relative adjustment skill": (
        "skills/catalog.json:20-21; app/Sources/HandsKit/Skills.swift:206-211,439",
    ),
}


def _sealed(path: Path) -> list[tuple[str, str, str, str]]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            ident, kind, text, expected = line.split("\t", 3)
            rows.append((ident, kind, text, expected.strip()))
    return rows


def _datasets(upstream: Path) -> dict[str, list[tuple[str, str, str, str]]]:
    frozen = upstream / "data/frozen"
    datasets = {
        "r4": _sealed(frozen / "hobbymac-sealed-test-r4.tsv"),
        "r1": _sealed(frozen / "hobbymac-sealed-test.tsv"),
        "r2": _sealed(frozen / "hobbymac-sealed-test-r2.tsv"),
        "r3": _sealed(frozen / "hobbymac-sealed-test-r3.tsv"),
        "calc": [],
        "settings": [],
    }
    settings = json.loads((frozen / "tasks.json").read_text(encoding="utf-8"))
    template = settings["goal_template"]
    for item in settings["dev"] + settings["held_out"]:
        datasets["settings"].append(
            (item["id"], "settings", template.format(dest=item["dest"]), item["dest"])
        )
    calc = json.loads((frozen / "calc-tasks.json").read_text(encoding="utf-8"))
    for index, (text, expected) in enumerate(calc["dev"], 1):
        datasets["calc"].append((f"D{index:02d}", "calc", text, str(expected)))
    index = 1
    for group, examples in calc["held_out"].items():
        for text, expected in examples:
            datasets["calc"].append((f"{group}-{index:02d}", "calc", text, str(expected)))
            index += 1
    return datasets


def _event_person(expected: str) -> str:
    fields = expected.split("|")
    return fields[-1].strip() if len(fields) >= 4 else "none"


def _gap_ids(datasets, catalog):
    result = {gap: {dataset: [] for dataset in DATASETS} for gap in GAP_EVIDENCE}
    skills = {item["name"]: item for item in catalog["skills"]}
    event_args = {arg["name"] for arg in skills["create_event"].get("args", [])}
    for dataset, rows in datasets.items():
        for ident, kind, text, expected in rows:
            gap = None
            if kind == "calc" and not any(
                skill in skills for skill in ("calculate", "calculator", "calculate_expression")
            ):
                gap = "Calculator/arithmetic has no executable skill or route"
            elif kind == "settings":
                gap = "Native System Settings navigation is not implemented"
            elif kind == "event":
                if _event_person(expected).casefold() != "none" and not (
                    {"attendee", "attendees", "invitee", "invitees"} & event_args
                ):
                    result["Event requests with people cannot create invitees"][dataset].append(ident)
            elif kind == "timer" and "start_timer" in skills:
                gap = "Countdown timers have no executable start_timer implementation"
            elif kind == "device" and expected.startswith("BRIGHTNESS_"):
                gap = "Directional brightness has no relative adjustment skill"
            if gap:
                result[gap][dataset].append(ident)
    return result


def _cell(ids: list[str]) -> str:
    return f"{len(ids)}: {', '.join(ids)}" if ids else "—"


def build(upstream: Path, catalog_path: Path) -> str:
    datasets = _datasets(upstream)
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    gaps = _gap_ids(datasets, catalog)
    ranked = sorted(
        gaps.items(),
        key=lambda item: (-len(item[1]["r4"]), item[0]),
    )
    r4_count = len(datasets["r4"])
    lines = [
        "# HobbyLM request coverage",
        "",
        f"Primary ranking is the {r4_count}-task sealed r4 live set. The remaining columns are separate frozen sources.",
        "Only implementation gaps confirmed by the catalog and execution path are ranked; model-routing quality needs live evaluation.",
        "",
        "| Rank | Confirmed gap | r4 live (IDs) | r1–r3 frozen (IDs by round) | calc-tasks (IDs) | System Settings (IDs) | Evidence |",
        "|---:|---|---|---|---|---|---|",
    ]
    for rank, (gap, sets) in enumerate(ranked, 1):
        old = "; ".join(
            f"{round_name} {_cell(sets[round_name])}"
            for round_name in ("r1", "r2", "r3") if sets[round_name]
        ) or "—"
        lines.append(
            f"| {rank} | {gap} | {_cell(sets['r4'])} | {old} | "
            f"{_cell(sets['calc'])} | {_cell(sets['settings'])} | {'; '.join(GAP_EVIDENCE[gap])} |"
        )
    lines.extend([
        "",
        "## Audited but not ranked",
        "",
        "- EventKit `create_event` has no calendar argument and always uses the default calendar "
        "(`skills/catalog.json:72-73`; `app/Sources/HandsKit/Skills.swift:575-584`). "
        "The replay harness therefore requires `Hobby Test` to be the default calendar; frozen tasks do not "
        "request choosing a different calendar.",
        "- Relative `remind me in` / `ping me in` tasks are included in the timer gap (T02, T04, T07 in r4): "
        "`create_reminder` requires a title and optional ISO due date, while `start_timer` has no HandsKit case. "
        "No separate timer-vs-reminder count is added.",
        "- Event text is routed through the catalog-backed `DecisionEngine.route` and `DecisionEngine.args`; "
        "datetime and duration arguments are normalized in `Orchestrator._coerce_typed`. No natural-language "
        "routing failure is claimed from the unused v0 regex router.",
        "- Relative volume, mute paraphrases, agenda lookup, and unknown-intent false positives are not "
        "ranked from the unused v0 regex router; these require live model evaluation.",
        "- Timezone-qualified date parsing and Hinglish remain unranked without a reproducible runtime result.",
        "- Catalog v2 also lists `bluetooth`, `lock_screen`, and `empty_trash` without HandsKit cases. "
        "`finance_review` and `advisor_prep` have brain-side modules, but `Orchestrator._skill` does not "
        "dispatch by the catalog `executor` field and HandsKit has no matching cases. These names do not "
        "occur in the frozen HobbyLM sets, so they are not ranked here "
        "(`skills/catalog.json:103-113`; `ml/src/brain/orchestrator.py:397-417`; "
        "`app/Sources/HandsKit/Skills.swift:157,381-383`).",
        "",
    ])
    return "\n".join(lines)


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
