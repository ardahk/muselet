"""Pass-20 repros (cloud/brain-5 003d1bb). Run from that checkout:
PYTHONPATH=ml/src:ml/tests pytest reviews/brain/tests/test_brain_pass20.py"""
import os

import pytest

from brain.orchestrator import abs_level

pathfind = pytest.importorskip("brain.pathfind")


def test_brain24_missing_file_not_resolved_to_sibling(tmp_path):
    for d in ("Desktop", "Documents", "Downloads"):
        (tmp_path / d).mkdir()
    (tmp_path / "Documents" / "invoice 2023.pdf").touch()
    # user asked to trash 'invoice 2024', which does not exist
    assert pathfind.resolve("invoice 2024", home=str(tmp_path)) == []


@pytest.mark.parametrize("text", [
    "turn the volume down for a min",
    "turn the brightness down in 5 min",
    "turn it up a little, my battery is full",
])
def test_brain16_min_full_anywhere_not_absolute(text):
    assert abs_level(text) is None
