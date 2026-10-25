"""Native tool-calling planner (`--planner-mode tools`): rendering via the real Qwen3.6 chat template, tool-call
parsing (XML + JSON forms), mapping to DSL lines `dsl.parse` accepts, corrective retry, history. No MLX: a fake
decode_fn returns completion text."""

import asyncio
import json
import threading
from pathlib import Path

import pytest
from jinja2.sandbox import ImmutableSandboxedEnvironment

from brain import dsl
from brain.catalog import Catalog
from brain.native_planner import (FALLBACK_LINE, NativeToolPlanner, ToolCallError, parse_tool_call, to_dsl)

TEMPLATE = (Path(__file__).parent / "fixtures" / "qwen36_chat_template.jinja").read_text()


class TemplateTok:
    """apply_chat_template over the shipped Qwen3.6 template (HF's jinja setup), chars as tokens."""

    def __init__(self):
        env = ImmutableSandboxedEnvironment(trim_blocks=True, lstrip_blocks=True,
                                            extensions=["jinja2.ext.loopcontrols"])
        env.filters["tojson"] = lambda x, **k: json.dumps(x, ensure_ascii=False)
        env.globals["raise_exception"] = lambda m: (_ for _ in ()).throw(ValueError(m))
        self.t = env.from_string(TEMPLATE)

    def apply_chat_template(self, messages, tools=None, add_generation_prompt=False, tokenize=True, **kw):
        assert not tokenize
        return self.t.render(messages=messages, tools=tools, add_generation_prompt=add_generation_prompt, **kw)

    def encode(self, s, add_special_tokens=False):
        return [ord(c) for c in s]


def xml_call(_tool, **args):
    params = "".join(f"<parameter={k}>\n{v if isinstance(v, str) else json.dumps(v)}\n</parameter>\n"
                     for k, v in args.items())
    return f"<tool_call>\n<function={_tool}>\n{params}</function>\n</tool_call>"


def make(replies, **kw):
    prompts = []
    replies = list(replies)

    def decode(prompt, budget, cancel):
        prompts.append((prompt, budget))
        return replies.pop(0), {"ttft_ms": 5.0, "tokens": 40, "decode_tok_s": 30.0,
                                "think": {"tokens": 30, "ms": 1.0, "text": "t", "closed": "model"}}
    p = NativeToolPlanner("fake-35b", Catalog.load(), tokenizer=TemplateTok(), decode_fn=decode, **kw)
    return p, prompts


def run_plan(p, goal="play jazz on youtube", obs='app: Google Chrome | window: "YouTube" | focused: #4\n'
             '#4 textfield "Search" value=""\nFinish when: a jazz video is playing', last_batch=None, **kw):
    async def go():
        q, loop = asyncio.Queue(), asyncio.get_running_loop()
        info = await loop.run_in_executor(None, lambda: p.plan(goal, obs, last_batch, q, loop,
                                                               threading.Event(), **kw))
        lines = []
        while (x := await q.get()) is not None:
            lines.append(x)
        return lines, info
    return asyncio.run(go())


def test_render_has_tools_brief_finish_and_observation():
    p, prompts = make(["thinking...\n</think>\n\n" + xml_call("press", ref=4)])
    lines, info = run_plan(p, hint="youtube")
    prompt = prompts[0][0]
    assert prompt.startswith("<|im_start|>system\n# Tools") and "<tools>" in prompt
    for name in ("press", "type", "keys", "scroll", "open_app", "open_url", "click", "wait", "ask", "confirm",
                 "done", "refuse", "skill"):
        assert f'"name": "{name}"' in prompt
    sys_part = prompt.split("<|im_end|>")[0]
    assert 'Goal: "play jazz on youtube"' in sys_part and "Finish when: a jazz video is playing" in sys_part
    assert "confirm first" in sys_part and "Hint: likely youtube" in sys_part
    user = prompt.split("<|im_start|>user\n")[1]
    assert '#4 textfield "Search"' in user and "Finish when" not in user
    assert prompt.endswith("<|im_start|>assistant\n<think>\n")        # thinking on
    assert prompts[0][1] == 1024
    assert lines == ["press #4"] and info["lines"] == ["press #4"]
    for k in ("ttft_ms", "decode_tok_s", "tokens", "plan_ms", "text", "think", "think_tokens"):
        assert k in info
    assert info["mode"] == "tools" and info["native"]["tool"] == "press"


def test_skill_tool_lists_only_system_skills():
    p, _ = make([])
    skill = next(t for t in p.tools if t["function"]["name"] == "skill")
    names = skill["function"]["parameters"]["properties"]["name"]["enum"]
    assert "set_volume" in names and "open_url" in names
    assert not set(names) & Catalog.load().app_skills()


def test_prefix_is_shared_by_every_prompt():
    p, prompts = make([xml_call("press", ref=4), xml_call("done", summary="ok")])
    run_plan(p)
    run_plan(p, goal="other goal", obs="app: Finder | window: x")
    prefix = p._prefix_text()
    assert prefix.endswith("\n\n") and all(pr.startswith(prefix) for pr, _ in prompts)


@pytest.mark.parametrize("raw,line", [
    (xml_call("press", ref=12), "press #12"),
    (xml_call("press", ref="#12"), "press #12"),
    (xml_call("type", ref=4, text="jazz", enter=True), 'type #4 "jazz" enter'),
    (xml_call("type", ref=4, text='say "hi"\nback\\slash'), 'type #4 "say \\"hi\\"\\nback\\\\slash"'),
    (xml_call("type", ref=4, text="multi\nline"), 'type #4 "multi\\nline"'),
    (xml_call("keys", combo="Command + Shift + N"), "keys cmd+shift+n"),
    (xml_call("keys", combo="enter"), "keys return"),
    (xml_call("scroll", ref=3, direction="down"), "scroll #3 down"),
    (xml_call("open_app", name="Google Chrome"), 'open "Google Chrome"'),
    (xml_call("open_url", url="https://youtube.com/results?search_query=jazz"),
     'url "https://youtube.com/results?search_query=jazz"'),
    (xml_call("click", description='the "Play" button', double=True), 'click "the \\"Play\\" button" double'),
    (xml_call("click", description="red dot"), 'click "red dot"'),
    (xml_call("wait", ms=500), "wait 500"),
    (xml_call("wait", ms=999999), "wait 10000"),
    (xml_call("ask", question="Which account?"), 'ask "Which account?"'),
    (xml_call("confirm", summary="Send the email to Mom?"), 'confirm "Send the email to Mom?"'),
    (xml_call("done", summary="Jazz is playing"), 'done "Jazz is playing"'),
    (xml_call("refuse", reason="Can't do that"), 'refuse "Can\'t do that"'),
    (xml_call("skill", name="set_volume", args={"level": 30}), "skill set_volume level=30"),
    (xml_call("skill", name="open_folder", args={"path": "~/My Docs"}), 'skill open_folder path="~/My Docs"'),
    # hermes JSON form, after a think block
    ('plan\n</think>\n\n<tool_call>\n{"name": "type", "arguments": {"ref": 7, "text": "a \\"q\\""}}\n'
     "</tool_call>", 'type #7 "a \\"q\\""'),
    ('<tool_call>{"name": "press", "arguments": "{\\"ref\\": 9}"}</tool_call>', "press #9"),
    ('<tool_call>{"name":"done","arguments":{"summary":"ok"}}</tool_call> trailing', 'done "ok"'),
])
def test_tool_call_maps_to_executable_dsl(raw, line):
    p, _ = make([])
    got = to_dsl(*parse_tool_call(raw), p.system_skills)
    assert got == line
    assert len(dsl.parse(got)) == 1


def test_mapped_text_roundtrips_exactly():
    text = 'he said "hi"\\n\tand\nleft'
    a = dsl.parse(to_dsl("type", {"ref": 2, "text": text}))[0]
    assert a["text"] == text


def test_first_tool_call_wins():
    raw = xml_call("press", ref=1) + "\n" + xml_call("press", ref=2)
    assert parse_tool_call(raw) == ("press", {"ref": 1})


@pytest.mark.parametrize("raw", [
    "I will press the search box.",
    "<tool_call>\n<function=fly>\n</function>\n</tool_call>",
    xml_call("press", ref="search"),
    "<tool_call>{not json}</tool_call>",
    xml_call("type", ref=4),
    xml_call("scroll", ref=4, direction="sideways"),
    xml_call("skill", name="whatsapp_send", args={"to": "Mom"}),
    xml_call("skill", name="set_volume", args={"level": {"x": 1}}),
    xml_call("done", summary=""),
])
def test_malformed_calls_raise(raw):
    p, _ = make([])
    with pytest.raises(ToolCallError):
        to_dsl(*parse_tool_call(raw), p.system_skills)


def test_malformed_then_retry_succeeds():
    p, prompts = make(["thought\n</think>\n\nI'd press search", xml_call("press", ref=4)])
    lines, info = run_plan(p)
    assert lines == ["press #4"] and info["native"]["retries"] == 1
    retry = prompts[1][0]
    assert "no valid tool call" in retry and "I'd press search" in retry and "thought" not in retry
    assert prompts[1][1] == 256


def test_malformed_twice_asks():
    p, prompts = make(["nothing", xml_call("fly")])
    lines, info = run_plan(p)
    assert lines == [FALLBACK_LINE] and len(prompts) == 2
    assert dsl.parse(FALLBACK_LINE)[0]["op"] == "ask"
    assert len(info["native"]["errors"]) == 2


def test_history_compact_last_8_and_reset_on_new_goal():
    p, prompts = make([xml_call("press", ref=4)] * 12)
    run_plan(p)
    for i in range(10):
        run_plan(p, last_batch=[f"press #{i} -> ok"])
    last = prompts[-1][0]
    assert "Last result:\n- press #9 -> ok" in last
    earlier = last.split("Earlier steps (oldest first):\n")[1].split("Last result:")[0]
    assert earlier.split("\n")[0] == "- press #1 -> ok" and "press #8 -> ok" in earlier
    assert "press #0 -> ok" not in earlier and "<think>\nthinking" not in last
    run_plan(p, goal="something else")
    assert "Earlier steps" not in prompts[-1][0] and "Last result" not in prompts[-1][0]


def test_history_kept_after_user_answer_and_begin_task_resets():
    p, prompts = make([xml_call("press", ref=4)] * 4)
    run_plan(p)
    run_plan(p, last_batch=["press #4 -> ok"])
    run_plan(p, goal='play jazz on youtube\nUser answer: "yes"', last_batch=['ask "which?" -> yes'])
    assert "- press #4 -> ok" in prompts[-1][0].split("Earlier steps")[1]
    p.begin_task()
    run_plan(p)
    assert "Earlier steps" not in prompts[-1][0]


def test_cli_planner_mode_flag(monkeypatch):
    from brain import cli
    got = {}

    async def fake_serve(*args, **kwargs):
        got.update(kwargs)
    monkeypatch.setattr(cli, "serve", fake_serve)
    monkeypatch.setattr(cli, "_resolve_model", lambda m: "m")
    cli.run_cmd(*cli.build_parser(["serve"]))
    assert got["planner_mode"] == "dsl" and got["planner_blind_mode"] is None
    cli.run_cmd(*cli.build_parser(["serve", "--planner-mode", "tools", "--planner-blind-mode", "tools"]))
    assert got["planner_mode"] == "tools" and got["planner_blind_mode"] == "tools"


def test_make_planner_tools_mode(monkeypatch):
    from brain import cli, native_planner
    seen = {}

    class Fake(native_planner.NativeToolPlanner):
        def __init__(self, path, catalog, **kw):
            seen.update(kw, path=path)

        def settings(self):
            return "mode=tools"
    monkeypatch.setattr(native_planner, "NativeToolPlanner", Fake)
    p = cli.make_planner("big", None, {"app_hints": True, "few_shot": "x"}, agentic_apps=True, mode="tools")
    assert isinstance(p, Fake) and seen["app_hints"] is True and seen["hidden_skills"]
    assert p.mode == "tools"
