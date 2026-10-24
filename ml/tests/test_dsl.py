import pytest

from brain import dsl
from brain.dsl import DSLError


CASES = [
    ('press #4', {"op": "press", "ref": 4}),
    ('type #4 "hello world" enter',
     {"op": "type", "ref": 4, "text": "hello world", "enter": True}),
    ('type #4 "hi"', {"op": "type", "ref": 4, "text": "hi", "enter": False}),
    ('keys cmd+shift+n', {"op": "keys", "combo": "cmd+shift+n"}),
    ('keys return', {"op": "keys", "combo": "return"}),
    ('scroll #2 down 3',
     {"op": "scroll", "ref": 2, "direction": "down", "n": 3}),
    ('scroll #2 up', {"op": "scroll", "ref": 2, "direction": "up", "n": 3}),
    ('click 100,200', {"op": "click", "x": 100.0, "y": 200.0,
                       "right": False, "double": False}),
    ('click 50.5,60 right', {"op": "click", "x": 50.5, "y": 60.0,
                             "right": True, "double": False}),
    ('click 1,2 double', {"op": "click", "x": 1.0, "y": 2.0,
                          "right": False, "double": True}),
    ('open "Safari"', {"op": "open", "name": "Safari"}),
    ('url "https://example.com/x?y=1"',
     {"op": "url", "url": "https://example.com/x?y=1"}),
    ('wait 500', {"op": "wait", "ms": 500}),
    ('ask "which file?"', {"op": "ask", "question": "which file?"}),
    ('confirm "Send to Mom?"', {"op": "confirm", "summary": "Send to Mom?"}),
    ('done "all set"', {"op": "done", "summary": "all set"}),
    ('refuse "unsafe"', {"op": "refuse", "reason": "unsafe"}),
    ('skill set_volume level=30',
     {"op": "skill", "name": "set_volume", "args": {"level": 30}}),
    ('skill mute on=true',
     {"op": "skill", "name": "mute", "args": {"on": True}}),
    ('skill new_folder parent=desktop name="my stuff"',
     {"op": "skill", "name": "new_folder",
      "args": {"parent": "desktop", "name": "my stuff"}}),
    ('script shell """echo hi"""',
     {"op": "script", "lang": "shell", "code": "echo hi"}),
]

PREDICATES = [
    'title~"Recents"',
    "focused #4",
    'value #4="hello"',
    'app "Finder"',
    'appears "Save"',
    "gone #7",
]


@pytest.mark.parametrize("line,want", CASES)
def test_parse_ops(line, want):
    assert dsl.parse(line) == [want]


def test_roundtrip():
    text = """press #4
type #4 "hello world" enter
keys cmd+shift+n
scroll #2 down 5
click 100,200 right
open "Safari"
url "https://x.io/a b"
wait 500
ask "which?"
confirm "Send it?"
done "done deal"
refuse "nope"
skill set_volume level=30
skill mute on=false"""
    # batch limit is 5, so parse each op line individually here
    actions = [dsl.parse(l)[0] for l in text.split("\n")]
    assert len(actions) == 14
    for a in actions:
        again = dsl.parse(dsl.serialize([a]))
        assert again == [a], (a, again)


def test_expect_attaches_to_previous():
    actions = dsl.parse('press #4\nexpect title~"Recents"')
    assert actions == [{"op": "press", "ref": 4,
                        "expect": 'title~"Recents"'}]
    s = dsl.serialize(actions)
    assert s == 'press #4\nexpect title~"Recents"'
    assert dsl.parse(s) == actions


@pytest.mark.parametrize("pred", PREDICATES)
def test_predicates(pred):
    assert dsl.parse(f"press #1\nexpect {pred}") == [
        {"op": "press", "ref": 1, "expect": pred}]


def test_multiline_script():
    text = 'script shell """line1\nline2"""'
    (a,) = dsl.parse(text)
    assert a == {"op": "script", "lang": "shell", "code": "line1\nline2"}


def test_escapes():
    (a,) = dsl.parse('type #1 "a \\"b\\" c"')
    assert a["text"] == 'a "b" c'
    assert dsl.parse(dsl.serialize([a])) == [a]


@pytest.mark.parametrize("bad,msg", [
    ("press 4", "expected #<ref>"),
    ("press", "press #<ref>"),
    ("type #4", "type #<ref>"),
    ("keys", "keys <combo>"),
    ("scroll #1 sideways", "bad direction"),
    ("click hi", "bad coords"),
    ("wait x", "wait <ms>"),
    ("expect gone #1", "no preceding action"),
    ("press #1\nexpect bogus", "bad expect predicate"),
    ("skill", "skill needs a name"),
    ("skill mute on", "key=value"),
    ("frobnicate", "unknown op"),
])
def test_bad_input(bad, msg):
    with pytest.raises(DSLError) as ei:
        dsl.parse(bad)
    assert ei.value.line >= 1
    assert msg in str(ei.value)


def test_line_numbers():
    with pytest.raises(DSLError) as ei:
        dsl.parse("press #1\nbogus")
    assert ei.value.line == 2


def test_max_batch():
    text = "\n".join(f"wait {i}" for i in range(6))
    with pytest.raises(DSLError) as ei:
        dsl.parse(text)
    assert "max 5" in str(ei.value)
