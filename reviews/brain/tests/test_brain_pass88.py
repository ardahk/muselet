"""Pass 88 repros (brain-75): a short literal reply containing a 'style'
word is no longer typed verbatim; the planner is told to compose its own."""
import pytest

from brain.agentic import hint


@pytest.mark.parametrize("about", [
    "thanks, that is very kind",
    "running short today",
    "sounds nice, see you then",
])
def test_literal_about_with_style_word_is_still_typed(about):
    assert f'type exactly: "{about}"' in hint("draft_email", {"about": about})
