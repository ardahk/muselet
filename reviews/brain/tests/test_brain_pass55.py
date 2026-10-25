"""brain-45: undo after window_layout replays an older layout for a different window."""
from brain.memory import eval_adapter


def _h(u, t, app, args):
    return {"utterance": u, "ctx": {"t": t, "app": app},
            "outcome": {"skill": "window_layout", "args": args, "ok": True}}


def test_undo_does_not_replay_other_windows_layout():
    hist = [_h("move safari to the left half", 100, "Safari",
               {"app": "Safari", "layout": "left"}),
            _h("move notes to the right half", 110, "Notes",
               {"app": "Notes", "layout": "right"})]
    out = eval_adapter("undo that", {"t": 120, "app": "Notes"}, hist)
    assert out["text"].casefold() != "move safari to the left half", out
