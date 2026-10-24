from pathlib import Path

from bench.hobbylm.coverage import build


ROOT = Path(__file__).resolve().parents[2]


def test_coverage_keeps_confirmed_gaps_and_ranks_pending_risks():
    report = build(
        ROOT / "bench/hobbylm/upstream",
        ROOT / "skills/catalog.json",
    )
    assert "| Rank | Confirmed gap |" in report
    assert "Calculator arithmetic uses the existing deterministic grammar" in report
    assert "Arithmetic word problems not parsed by calc" in report
    assert "Calculator/arithmetic has no executable skill or route" not in report
    assert "Countdown timers have no executable start_timer implementation" not in report
    assert "Directional brightness: brain done; HandsKit delta pending (lead's Swift batch)" not in report
    assert "Directional brightness is implemented through the HandsKit delta argument" in report
    assert "Native System Settings navigation is not implemented" in report
    assert "## Risks pending live evidence" in report
    assert "unverified until the Muselet live replay runs" in report
    assert "12: N01 (`web_search`)" in report
    assert "N02 (`send_message`)" in report
    assert "10: E03; E04; E09; E11; E13; E14; E16; E18; E25; E30" in report
    assert "3: T02; T04; T07" in report
    assert "1: A03" in report
    assert "3: C07; D08; A02" in report
    assert "`todays_agenda`/`ANSWER`" in report
