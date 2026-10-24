"""Build the DeskMind diagnostic task reference from its pinned task YAMLs."""

from __future__ import annotations

import argparse
from pathlib import Path

GLOSSES = {
    "G01": "Sort the Finder files into the requested order.",
    "G02": "Edit the requested text in TextEdit.",
    "G03": "Find and extract the requested information in Safari.",
    "G04": "Enter the exact requested Chinese text.",
    "G05": "Ask for clarification when the request is ambiguous.",
    "G06": "Avoid acting on the wrong target.",
    "G07": "Create a new Finder folder with the requested name.",
    "G08": "Move only the requested Finder item.",
    "G09": "Navigate down to the requested Finder location.",
    "G10": "Navigate back up to the requested Finder location.",
    "G11": "Scroll through a long page to find the requested item.",
    "G12": "Cancel the task midway and stop acting.",
    "G13": "Complete the requested end-to-end round trip.",
}


def render(task_dir: Path) -> str:
    import yaml

    rows = []
    for path in sorted(task_dir.glob("*.yaml")):
        task = yaml.safe_load(path.read_text(encoding="utf-8"))
        ident = str(task["id"])
        goals = GLOSSES.get(ident, "English gloss not available.")
        lines = [
            f"## {ident}",
            "",
            f"- **Goal (original):** {task['goal']}",
            f"- **English gloss:** {goals}",
            f"- **Fixture:** `{task.get('fixture') or '(none)'}`",
            "- **Checkpoints:**",
        ]
        for cp in (task.get("grade") or {}).get("checkpoints", []):
            lines.append(
                f"  - `{cp.get('name', '(unnamed)')}` weight={cp.get('weight', 1)} "
                f"critical={bool(cp.get('critical', False))}: `{cp['check']}`"
            )
        for index, behavior in enumerate((task.get("grade") or {}).get("behaviour", []), 1):
            lines.append(f"  - `behaviour[{index - 1}]` process checkpoint: `{behavior}`")
        lines.append("- **Guards:**")
        guards = (task.get("grade") or {}).get("guards", [])
        lines.extend(f"  - `{guard}`" for guard in guards) if guards else lines.append("  - (none)")
        lines.append("- **Forbids:**")
        forbids = (task.get("grade") or {}).get("forbid", [])
        lines.extend(f"  - `{forbid}`" for forbid in forbids) if forbids else lines.append("  - (none)")
        lines.append("- **Sentinels:**")
        sentinels = task.get("sentinels", [])
        lines.extend(f"  - `{sentinel}`" for sentinel in sentinels) if sentinels else lines.append("  - (none)")
        rows.extend(lines + [""])
    return "# DeskMind diagnostic tasks\n\n" + "\n".join(rows)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task-dir", type=Path, default=Path("/home/ubuntu/ext/deskmind-ai__bench/tasks/diag"))
    parser.add_argument("--out", type=Path, default=Path(__file__).resolve().parent / "tasks.md")
    args = parser.parse_args(argv)
    args.out.write_text(render(args.task_dir), encoding="utf-8")
    print(args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
