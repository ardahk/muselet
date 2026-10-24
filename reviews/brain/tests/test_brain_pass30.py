"""Pass 30 (cloud/brain-6 780f49d): grounded-click / Enter send gates.
Runs against brain-6 (needs ml/tests/test_grounder_wire.py helpers)."""
import pytest

sendgate = pytest.importorskip("brain.sendgate")
tgw = pytest.importorskip("test_grounder_wire")


@pytest.mark.parametrize("app,window", [
    ("Microsoft Outlook", "Inbox"),          # native Outlook: not in _COMPOSER_NAMES
    ("Google Chrome", "Inbox - Outlook"),    # Outlook web: not in _BROWSER_TITLE_RE
    ("Google Chrome", "Messaging | LinkedIn"),
])
def test_brain27_icon_only_send_in_unlisted_composer(tmp_path, app, window):
    # blind AX (no labeled element at point) + icon-only send button (OCR reads nothing)
    orch, server = tgw._safety_gate_orch(tmp_path, app=app, window=window,
                                         elements=[], ocr_text="")
    server.confirm_yes = False
    tgw._click(orch, target="the paper plane icon")
    assert server.confirms or not server.acts(), \
        f"{app} / {window}: icon-only send clicked with no confirm: {server.acts()}"


@pytest.mark.parametrize("window", [
    "nba teams - Google Search",
    "How to zoom in on a Mac - Google Search",
    "traffic signal timing - Wikipedia",
    "Messages from the CEO - The Verge",
])
def test_brain28_browser_title_words_not_composer(window):
    assert not sendgate.is_composer_app("Google Chrome", window), \
        f"Chrome '{window}' treated as a message composer: every Enter/grounded click confirms"
