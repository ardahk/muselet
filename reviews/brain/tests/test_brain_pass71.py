"""brain-53 (wip/local 323d274): finish.finish_when gives an end state that only covers the first step of compound goals, or names the wrong kind of end state; the planner loop adds it as 'Finish when:' to every planner turn."""
import pytest

fw = pytest.importorskip("brain.finish")


@pytest.mark.parametrize("goal,bad", [
    ("open the email from john and reply yes", "is frontmost"),
    ("find a recipe and email it to mom", "a results page for"),
    ("start a 5 minute timer", "is frontmost"),
    ("navigate to settings", "a route to"),
    ("put the report in my bag folder", "added to the cart"),
])
def test_finish_criterion_matches_goal(goal, bad):
    crit = fw.finish_when(goal)
    assert crit is None or bad not in crit, crit
