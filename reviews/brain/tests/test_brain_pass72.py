"""brain-54 (cloud/agentic-loop 9b2e512): finish.evidence is accepted as done verification in place of expect/model checks, but its tests are weak: any 'playing' in script stdout, any Directions/Route text, or subject words of only the first step of a compound goal."""
import pytest

fin = pytest.importorskip("brain.finish")
if not hasattr(fin, "evidence"):
    pytest.skip("no finish.evidence on this branch", allow_module_level=True)


def test_not_playing_stdout_is_not_play_evidence():
    assert not fin.evidence("play", "jazz", {}, script_stdout="not playing")


def test_maps_directions_button_is_not_a_route():
    obs = {"app": "Google Chrome", "window": "Google Maps",
           "text": '#12 button "Directions"\n#13 textfield "Search Google Maps"'}
    assert not fin.evidence("directions", "the airport", obs)


def test_first_step_of_compound_goal_is_not_done():
    goal = "search for flights to tokyo and book the cheapest one"
    crit = fin.criterion(goal)
    obs = {"app": "Google Chrome", "window": "flights - Google Search",
           "url": "https://www.google.com/search?q=flights"}
    assert crit is None or not fin.evidence(crit[0], crit[1], obs), crit
