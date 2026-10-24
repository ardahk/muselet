"""Generate the public external-evaluation utterance corpus deterministically."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def collect(hobby_home: Path, deskmind_bench: Path):
    frozen = hobby_home / "data/frozen"
    records = []
    seen_sealed = set()
    for round_name in ("r1", "r2", "r3", "r4"):
        name = "hobbymac-sealed-test.tsv" if round_name == "r1" else f"hobbymac-sealed-test-{round_name}.tsv"
        for line in (frozen / name).read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            ident, _kind, text, _expected = line.split("\t", 3)
            key = (ident, text)
            if key not in seen_sealed:
                seen_sealed.add(key)
                records.append({"source": f"hobbylm/sealed-{round_name}", "id": ident, "text": text})

    settings = json.loads((frozen / "tasks.json").read_text(encoding="utf-8"))
    for item in settings["dev"] + settings["held_out"]:
        records.append({
            "source": "hobbylm/system-settings",
            "id": item["id"],
            "text": settings["goal_template"].format(dest=item["dest"]),
        })

    calc = json.loads((frozen / "calc-tasks.json").read_text(encoding="utf-8"))
    for index, (text, _answer) in enumerate(calc["dev"], 1):
        records.append({"source": "hobbylm/calc-tasks/dev", "id": f"D{index:02d}", "text": text})
    for group, items in sorted(calc["held_out"].items()):
        for index, (text, _answer) in enumerate(items, 1):
            records.append({"source": "hobbylm/calc-tasks/held-out", "id": f"{group}-{index:02d}", "text": text})

    import yaml

    task_root = deskmind_bench / "tasks"
    for path in sorted(task_root.rglob("*.yaml")):
        task = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(task, dict) or not task.get("goal"):
            continue
        task_set = path.parent.relative_to(task_root).as_posix()
        records.append({
            "source": f"deskmind/{task_set}",
            "id": str(task.get("id", path.stem)),
            "text": str(task["goal"]).strip(),
        })
    return sorted(records, key=lambda item: (item["source"], item["id"], item["text"]))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hobby-home", type=Path, default=Path("/home/ubuntu/ext/hobbylm"))
    parser.add_argument("--deskmind-bench", type=Path, default=Path("/home/ubuntu/ext/deskmind-ai__bench"))
    parser.add_argument("--out", type=Path, default=Path(__file__).with_name("utterances.jsonl"))
    args = parser.parse_args(argv)
    records = collect(args.hobby_home, args.deskmind_bench)
    args.out.write_text(
        "".join(json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n" for item in records),
        encoding="utf-8",
    )
    print(f"{len(records)} utterances -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
