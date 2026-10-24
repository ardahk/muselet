"""Build a ranked coverage map from frozen HobbyLM and extension sets."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from bench.hobbylm.vendor import verify_provenance
VENDORED_UPSTREAM = Path(__file__).resolve().parent / "upstream"
DATASETS = ("r4", "r1", "r2", "r3", "calc", "settings")
GAP_EVIDENCE = {
    "Arithmetic word problems not parsed by calc": (
        "ml/tests/test_hobby_gaps.py:26-30; ml/src/brain/calc.py:437-453",
    ),
    "Native System Settings navigation is not implemented": (
        "skills/catalog.json:10-114; app/Sources/HandsKit/Skills.swift:360-520",
    ),
    "Event requests with people cannot create invitees": (
        "skills/catalog.json:74-79; app/Sources/HandsKit/Skills.swift:922-944",
    ),
}
UNHANDLED_R4_CALC = {
    "C07", "C08", "C09", "C10", "C11", "C12", "C13", "C14", "C15",
    "C17", "C20", "C22", "C23", "C24", "C25", "C26", "C27", "C28",
    "C29", "C30",
}


def _sealed(path: Path) -> list[tuple[str, str, str, str]]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            ident, kind, text, expected = line.split("\t", 3)
            rows.append((ident, kind, text, expected.strip()))
    return rows


def _datasets(upstream: Path) -> dict[str, list[tuple[str, str, str, str]]]:
    verify_provenance(VENDORED_UPSTREAM)
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
            if kind == "settings":
                gap = "Native System Settings navigation is not implemented"
            elif kind == "event":
                if _event_person(expected).casefold() != "none" and not (
                    {"attendee", "attendees", "invitee", "invitees"} & event_args
                ):
                    result["Event requests with people cannot create invitees"][dataset].append(ident)
            elif kind == "calc" and ident in UNHANDLED_R4_CALC:
                gap = "Arithmetic word problems not parsed by calc"
            if gap:
                result[gap][dataset].append(ident)
    return result


def _cell(ids: list[str]) -> str:
    return f"{len(ids)}: {', '.join(ids)}" if ids else "—"


def _pending_risks(datasets, catalog):
    r4 = datasets["r4"]
    by_id = {ident: (kind, text) for ident, kind, text, _ in r4}
    catalog_skills = {item["name"] for item in catalog["skills"]}
    none_candidates = {
        "N01": "web_search",
        "N02": "send_message",
        "N03": "open_url",
        "N04": "MULTI_STEP",
        "N07": "play_music",
        "N08": "finance_review",
        "N09": "open_app",
        "N10": "start_timer",
        "N11": "find_file",
        "N13": "web_search",
        "N14": "web_search",
        "N16": "web_search",
    }
    none = []
    for ident, candidate in none_candidates.items():
        if ident not in by_id or by_id[ident][0] != "none":
            continue
        if candidate == "MULTI_STEP" or candidate in catalog_skills:
            none.append(f"{ident} (`{candidate}`)")

    timezone = [
        ident for ident, kind, text, _ in r4
        if kind == "event"
        and re.search(r"\b(?:IST|GMT|UTC|PST|PDT|EST|EDT|CST|CDT|MST|MDT|CET|CEST|SGT)\b", text, re.I)
    ]
    mixed_words = re.compile(r"\b(?:kal|parso|aaj|abhi|kripya|karo|karna|hai|hain|mera|meri|mujhe|bhai)\b", re.I)
    hinglish = [
        ident for ident, _, text, _ in r4 if mixed_words.search(text)
    ]
    relative = [
        ident for ident, kind, text, _ in r4
        if kind == "timer" and re.search(r"\b(?:remind me|ping me)\b.*\b(?:in|after)\b", text, re.I)
    ]
    agenda = [
        ident for ident, kind, _, _ in r4
        if ident.startswith("A03") and kind == "app"
    ]
    risks = [
        ("None-set requests may hit an acting catalog route (HobbyLM grades any action as failure)", none),
        ("Timezone-qualified event times may be parsed or normalized differently", timezone),
        ("Relative reminder wording may route as a timer or reminder", relative),
        ("A03-style requests may route to `todays_agenda`/`ANSWER` instead of leaving Calendar frontmost", agenda),
        ("Hinglish/code-mixed requests may route differently", hinglish),
    ]
    return sorted(risks, key=lambda item: (-len(item[1]), item[0]))


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
    pending = _pending_risks(datasets, catalog)
    lines.extend([
        "",
        "## Risks pending live evidence",
        "",
        "These are hypotheses, not confirmed gaps. They remain unverified until the Muselet live replay runs.",
        "Ranked by the number of matching r4 tasks; `none` IDs include the likely catalog skill or route.",
        "",
        "| Rank | Unverified risk | r4 count (IDs / likely route) |",
        "|---:|---|---|",
    ])
    for rank, (risk, ids) in enumerate(pending, 1):
        details = "; ".join(ids) if ids else "—"
        lines.append(f"| {rank} | {risk} | {len(ids)}: {details} |")
    lines.extend([
        "",
        "## Audited but not ranked",
        "",
        "- EventKit `create_event` has no calendar argument and always uses the default calendar "
        "(`skills/catalog.json:74-79`; `app/Sources/HandsKit/Skills.swift:922-944`). "
        "The replay harness therefore requires `Muselet Bench` to be a local default calendar; frozen tasks do not "
        "request choosing a different calendar.",
        "- Countdown timers are executable through `start_timer`; the replay grades its successful RPC result "
        "and discloses whether timers were canceled. Relative reminder wording remains a live-routing risk.",
        "- Event text is routed through the catalog-backed `DecisionEngine.route` and `DecisionEngine.args`; "
        "datetime and duration arguments are normalized in `Orchestrator._coerce_typed`. No natural-language "
        "routing failure is claimed from the unused v0 regex router.",
        "- Relative volume, mute paraphrases, agenda lookup, and unknown-intent false positives are not "
        "ranked from the unused v0 regex router; these require live model evaluation.",
        "- Timezone-qualified date parsing and Hinglish are listed only as unverified live-evidence risks above.",
        "- Calculator arithmetic uses the existing deterministic grammar; unhandled r4 word problems are ranked "
        "above. Timer, Bluetooth, lock-screen, "
        "and empty-Trash paths are implemented in HandsKit. Brain-executor dispatch is present in the orchestrator. "
        "Directional brightness uses brain-5's argument inference (`ml/src/brain/argfix.py:17-22`; "
        "`ml/src/brain/orchestrator.py:537-558`) and HandsKit's `set_brightness {delta}` implementation "
        "(`app/Sources/HandsKit/Skills.swift:418-435`). Event invitees and native System Settings navigation "
        "remain unimplemented. "
        "Evidence: `ml/src/brain/calc.py:437-453`; "
        "`ml/src/brain/orchestrator.py:296-302,346-356,405-422,433-481,695-747`; "
        "`app/Sources/HandsKit/Skills.swift:373-380,471-482`.",
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
