"""brain-46: 'bump' in argfix._UP makes 'bump it down' ambiguous (up and down both match)."""
from brain import argfix


def test_bump_down_is_negative():
    for s in ("bump it down", "bump the brightness down a bit",
              "bump the volume down a little"):
        assert argfix.vague_delta(s) == -10, s
