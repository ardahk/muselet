"""Copy the pinned Apache-2.0 HobbyLM evaluation harness and frozen inputs."""

from __future__ import annotations

import argparse
import hashlib
import re
import shutil
from pathlib import Path

REVISION = "4ea1389b68f5a6f7ec72200543fd8374c14d4526"
HF_REPO = "Hobbylm/hobbylm-1B-computer-use"
FILES = [
    "LICENSE",
    "README.md",
    "hobby/hobbymac_run.py",
    "hobby/hobbymac_score.py",
    "hobby/calendar_tool.py",
    "hobby/hobbymac_data.py",
    "hobby/mcp_client.py",
    "hobby/brightness.swift",
    "hobby/calc_checker.swift",
    "hobby/checker.swift",
    "hobby/media_key.swift",
    "scripts/setup.sh",
]


def vendor(source: Path, destination: Path) -> list[tuple[str, str]]:
    files = list(FILES)
    files.extend(str(path.relative_to(source)) for path in sorted((source / "data/frozen").rglob("*")) if path.is_file())
    files.extend(
        str(path.relative_to(source)) for path in sorted((source / "data").glob("hobbymac-regex-sealed*.json"))
    )
    destination.mkdir(parents=True, exist_ok=True)
    copied = []
    for relative in sorted(set(files)):
        source_path = source / relative
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, target)
        digest = hashlib.sha256(target.read_bytes()).hexdigest()
        copied.append((relative, digest))
    readme = (source / "README.md").read_text(encoding="utf-8")
    github = sorted(set(re.findall(r"https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", readme)))
    lines = [
        "# HobbyLM vendored files",
        "",
        f"- Hugging Face source: [`{HF_REPO}`](https://huggingface.co/{HF_REPO})",
        f"- Frozen revision: `{REVISION}`",
        "- License: Apache-2.0; the upstream `LICENSE` is included verbatim.",
        '- Round 4 is the 125-request sealed live set ("90/125" completed pass-bar target).',
        "- Other frozen sets include r1 (95), r2 (95), r3 (107), System Settings navigation, Calculator tasks, prompts, and pass-bar amendments.",
        "- GitHub links present in the upstream model card: " + (", ".join(f"`{url}`" for url in github) if github else "none"),
        "",
        "| File | SHA-256 |",
        "|---|---|",
    ]
    lines.extend(f"| `{name}` | `{digest}` |" for name, digest in copied)
    (destination / "PROVENANCE.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return copied


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=Path("/home/ubuntu/ext/hobbylm"))
    parser.add_argument("--destination", type=Path, default=Path(__file__).resolve().parent / "upstream")
    args = parser.parse_args(argv)
    copied = vendor(args.source, args.destination)
    print(f"Vendored {len(copied)} files from {args.source} at {REVISION}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
