"""Repro for sendgate search/find early-return (main 4f94e42, 05d42d2).
Run: git show origin/main:ml/src/brain/sendgate.py > sendgate.py; pytest this file."""
from sendgate import enter_sends

def test_composer_with_search_word_still_sends():
    # Slack channel composer label; Enter sends here
    assert enter_sends("Slack", "Slack", "AXTextArea", "Message #search-team")
    assert enter_sends("Messages", "Messages", "AXTextArea", "Message Find My Crew")
