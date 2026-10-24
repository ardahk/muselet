import shutil
from pathlib import Path

import pytest

from bench.hobbylm.vendor import verify_provenance

UPSTREAM = Path(__file__).resolve().parents[1] / "hobbylm" / "upstream"


def test_vendored_hobby_files_match_provenance():
    verify_provenance(UPSTREAM)


def test_provenance_rejects_tampered_copy(tmp_path):
    target = tmp_path / "upstream"
    shutil.copytree(UPSTREAM, target, ignore=shutil.ignore_patterns("__pycache__"))
    changed = target / "data/frozen/hobbymac-sealed-test-r4.tsv"
    changed.write_text(changed.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="hobbymac-sealed-test-r4.tsv: expected"):
        verify_provenance(target)
