import pytest

from bench.deskmind.run_muselet import HANDS_COMMIT, _check_hands_commit


@pytest.mark.parametrize(
    ("reported_commit", "matches_pin"),
    [(HANDS_COMMIT, True), ("deadbeef", False)],
)
def test_hands_commit_check_uses_explicit_deskmind_python(
    tmp_path, reported_commit, matches_pin,
):
    interpreter = tmp_path / "python"
    interpreter.write_text(
        f"#!/bin/sh\nprintf '%s\\n' '{reported_commit}'\n",
        encoding="utf-8",
    )
    interpreter.chmod(0o755)

    if matches_pin:
        assert _check_hands_commit(str(interpreter)) == HANDS_COMMIT
    else:
        with pytest.raises(RuntimeError, match=f"found {reported_commit}"):
            _check_hands_commit(str(interpreter))
