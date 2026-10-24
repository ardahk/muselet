import pytest

from test_planner_loop import _diff_orch, run, trace_for


@pytest.mark.parametrize("turns", [
    [['done "finished"']],
    [["press #1"], ['done "finished"']],
    [["press #1", 'expect appears "Saved"', "press #4"], ['done "finished"']],
], ids=["empty_task", "unverified_action", "last_action_has_no_expect"])
def test_brain11_done_without_evidence_is_unverified(tmp_path, turns):
    orch = _diff_orch(tmp_path, turns, lambda p: {"ok": True})
    assert run(orch._planner_loop("finish", trace_for(orch))) == "unverified"
    assert orch.server.uis[-1] == "idle"
    assert "success" not in orch.server.uis
    assert any("done -> failed: needs evidence (add expect <predicate>)" in line
               for msg in orch.planner.user_msgs for line in msg["last_batch"] or [])


@pytest.mark.parametrize("result", [True, False, "error"])
def test_done_own_expect_requires_passing_verify(tmp_path, result):
    orch = _diff_orch(tmp_path, [['done "finished"', 'expect appears "Saved"']],
                      lambda p: {"ok": True})

    def verify(params):
        assert params == {"expect": 'appears "Saved"'}
        if result == "error":
            raise RuntimeError("verify unavailable")
        return {"ok": result, "observed": "Saved" if result else "missing"}

    orch.server.handlers["verify"] = verify
    assert run(orch._planner_loop("finish", trace_for(orch))) == (
        "ok" if result is True else "unverified")
    assert orch.server.uis[-1] == ("success" if result is True else "idle")
    assert orch.server.methods().count("verify") == (1 if result is True else 2)


def test_done_can_recover_with_own_expect_after_rejection(tmp_path):
    orch = _diff_orch(tmp_path, [['done "unverified"'],
                                ['done "verified"', 'expect appears "Saved"']],
                      lambda p: {"ok": True})
    assert run(orch._planner_loop("finish", trace_for(orch))) == "ok"
    assert orch.server.said[-1] == "verified"
    assert orch.server.methods() == ["observe", "observe", "verify"]
