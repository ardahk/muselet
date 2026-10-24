"""ux-10: planner-path confirm summary reads the wrong arg key and leaks full paths."""
import asyncio, sys
sys.path.insert(0, "ml/src")
from brain.orchestrator import Orchestrator


class T:
    def __getattr__(self, n): return lambda *a, **k: {"decisions": []}


def summ(a):
    return asyncio.run(Orchestrator(object(), tracer=T())._confirm_summary(a))


def test_send_message_names_body():
    s = summ({"op": "skill", "name": "send_message", "args": {"to": "Mom", "body": "running late"}})
    assert "None" not in s and "running late" in s, s   # got: Text Mom: "None"?


def test_trash_uses_basename():
    s = summ({"op": "skill", "name": "move_to_trash", "args": {"path": "/Users/a/Desktop/Q3 Budget.numbers"}})
    assert "/Users" not in s, s


def test_fallback_is_a_question():
    s = summ({"op": "skill", "name": "empty_trash", "args": {}})
    assert ".?" not in s, s   # got: Permanently empty the Trash.?
