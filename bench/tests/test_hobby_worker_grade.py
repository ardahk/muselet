from bench.hobbylm import replay


class FakeHelper:
    @staticmethod
    def unused():
        return None


def test_worker_strict_grade_uses_parent_snapshot_not_upstream_completion(monkeypatch):
    monkeypatch.setattr(
        replay, "_grade_final_state",
        lambda *_args, **_kwargs: (True, {"front": "Calculator"}),
    )
    result = replay._worker_snapshot_grade(
        FakeHelper(),
        {"kind": "app", "expected": "OPEN Calculator", "text": "open calculator"},
        {},
        {"front": "Calculator"},
        first_action=True,
    )
    assert result["passed"] is True
    assert "upstream_completed" not in result


def test_worker_grade_marks_missing_required_snapshot_ungradable():
    result = replay._worker_snapshot_grade(
        FakeHelper(),
        {"kind": "none", "expected": "NONE", "text": "do nothing"},
        {"bright": 50},
        {"bright": 50},
    )
    assert result["passed"] is False
    assert result["ungradable"] is True
    assert "calendar_events" in result["missing_snapshots"]
