#!/usr/bin/env python3
"""Upload built planner demo files to a private Hugging Face dataset."""

from __future__ import annotations

import argparse
from pathlib import Path

from huggingface_hub import HfApi


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dir", required=True, type=Path)
    parser.add_argument("--repo", default="jonsnov/muselet-planner-demos-v1")
    args = parser.parse_args()
    directory = args.dir.expanduser()
    if not directory.is_dir():
        parser.error(f"not a directory: {directory}")

    api = HfApi()
    api.create_repo(repo_id=args.repo, repo_type="dataset", private=True, exist_ok=True)
    commit = api.upload_folder(
        repo_id=args.repo,
        repo_type="dataset",
        folder_path=str(directory),
        allow_patterns=["*.jsonl.gz", "meta.json", "README.md"],
    )
    print(commit.oid)


if __name__ == "__main__":
    main()
