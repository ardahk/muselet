"""brain-69 (main 05d42d2): enter_sends() returns False whenever the focused
label contains 'search'/'find', before the composer-app check, so a chat
composer whose label names a channel/person with those words loses the
Enter-sends confirmation gate."""
import pytest
from brain.sendgate import enter_sends


@pytest.mark.parametrize("app,window,role,label", [
    ("Slack", "search-infra (Channel) - Acme - Slack", "textarea",
     "Message #search-infra"),
    ("Discord", "#find-a-teammate | Server", "textarea",
     "Message #find-a-teammate"),
])
def test_composer_named_after_search_channel_still_gates_enter(
        app, window, role, label):
    assert enter_sends(app, window, role, label)
