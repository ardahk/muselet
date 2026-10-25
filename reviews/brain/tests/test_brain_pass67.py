"""brain-50: premiere_edit.parse_request claims any utterance that mentions 'premiere' (any app) or says export/render/cut/marker while Premiere is front; _engine_route runs it before the router."""
import pytest

pe = pytest.importorskip("brain.tools.premiere_edit")


@pytest.mark.parametrize("text,app", [
    ("search google for premiere pro export settings", "Safari"),
    ("how do I render faster in premiere", "Safari"),
    ("remind me to export the video at 5pm", "Adobe Premiere Pro 2026"),
    ("add a calendar marker for the premiere on friday", "Calendar"),
])
def test_non_edit_requests_are_not_premiere_edits(text, app):
    assert pe.parse_request(text, {"app": app}) is None, pe.parse_request(text, {"app": app})
