import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SUITE = ROOT / "evals" / "live_premiere.jsonl"


def test_premiere_live_turns_have_mechanical_preconditions_and_external_checks():
    cases = [json.loads(line) for line in SUITE.read_text().splitlines() if line.strip()]
    assert {case["id"] for case in cases} == {
        "premiere-demo-sequence", "premiere-negative-routing"}
    for case in cases:
        assert case.get("precondition")
        turns = case.get("turns") or [{"check": case.get("check", [])}]
        for turn in turns:
            checks = turn.get("check", [])
            assert checks
            assert any(
                isinstance(check, dict)
                and {"applescript", "jxa", "shell", "rpc"} & check.keys()
                for check in checks
            )
            assert all("trace_say" not in check for check in checks)

    demo = next(case for case in cases if case["id"] == "premiere-demo-sequence")
    assert len(demo["turns"]) == 6
    assert all(turn["confirm_reply"] is True for turn in demo["turns"])
    assert [turn["utterance"] for turn in demo["turns"]] == [
        "import the clips from my Desktop Footage folder",
        "cut the clip at the playhead",
        "add a cross dissolve",
        "speed this up to 150%",
        "add a marker here called intro",
        "export a 1080p H.264 to the Desktop",
    ]
