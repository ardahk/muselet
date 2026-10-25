"""brain-65 (main 3e323a9 / 7010ee0): Spotify play evidence needs the goal
subject inside 'player state + current track name', so artist/genre/playlist
requests can't pass the done check even when the right music plays.
brain-66 (cloud/agentic-fixes2 b9cd089): agentic.hint appends
'type exactly: "<about>"' for draft_email, so the reply topic becomes the
literal text to type."""
import pytest
from brain import finish


@pytest.mark.parametrize("goal,stdout", [
    ("play taylor swift on spotify", "playing Shake It Off"),
    ("play some jazz on spotify", "playing Take Five"),
    ("play my discover weekly playlist on spotify", "playing Midnight City"),
])
def test_spotify_artist_genre_playlist_can_be_done(goal, stdout):
    crit = finish.criterion(goal)
    assert crit and crit[0] == "play"
    assert finish.evidence("play", crit[1], {"text": ""},
                           script_stdout=stdout, goal=goal)


def test_draft_email_topic_is_not_literal_text():
    agentic = pytest.importorskip("brain.agentic")
    if not hasattr(agentic, "content"):
        pytest.skip("no content hint on this branch")
    h = agentic.hint("draft_email", {"to": "john", "about": "the meeting"})
    assert 'type exactly: "the meeting"' not in h
