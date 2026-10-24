import argparse
import json
from pathlib import Path

from bench.live.run_live import _dry_run, _filter_reasons, _load_suite


ROOT = Path(__file__).resolve().parents[2]
SUITE = ROOT / "evals/live_t1.jsonl"


def _args(**overrides):
    values = {
        "suite": SUITE,
        "tier": set(),
        "category": set(),
        "id": set(),
        "include_manual": False,
        "include_pending": False,
        "allow_user_ok": False,
        "offline": False,
        "repeat": 2,
    }
    values.update(overrides)
    return argparse.Namespace(**values)


def test_dry_run_includes_all_live_cases_and_tier_counts(capsys):
    cases = _load_suite(SUITE)
    assert len(cases) == 43
    assert _dry_run(cases, _args()) == 0
    plan = json.loads(capsys.readouterr().out)
    assert plan["tier_counts"] == {"T1": 33, "T2": 10}
    assert plan["cases_by_repeat"] == 86
    assert len(plan["case_plan"]) == 43
    assert all("{{" not in json.dumps(row["resolved"]) for row in plan["case_plan"])
    assert all("document_apps" in row for row in plan["case_plan"])
    assert any(row["document_apps"] for row in plan["case_plan"])


def test_filters_report_manual_pending_online_and_user_consent_skips():
    cases = _load_suite(SUITE)
    args = _args()
    manual = next(case for case in cases if case.get("manual"))
    pending = next(case for case in cases if case.get("pending"))
    online = next(case for case in cases if case.get("online"))
    requires_ok = next(case for case in cases if case.get("requires_user_ok"))
    assert "manual" in _filter_reasons(manual, args)[0]
    assert "pending" in _filter_reasons(pending, args)[0]
    assert any("consent" in reason for reason in _filter_reasons(requires_ok, args))
    assert "manual" not in _filter_reasons(manual, _args(include_manual=True))
    assert "pending" not in _filter_reasons(pending, _args(include_pending=True))
    assert "online" in _filter_reasons(online, _args(offline=True))[0]
    assert not _filter_reasons(
        requires_ok, _args(include_pending=True, allow_user_ok=True)
    )


def test_tier_category_and_id_filters_are_combined():
    case = {"id": "a", "tier": "T1", "category": "system"}
    assert not _filter_reasons(case, _args(tier={"T1"}, category={"system"}, id={"a"}))
    assert "tier filter" in _filter_reasons(case, _args(tier={"T2"}))
    assert "category filter" in _filter_reasons(case, _args(category={"apps"}))
    assert "id filter" in _filter_reasons(case, _args(id={"b"}))
