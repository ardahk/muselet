"""Draft-email parsing, composition, and explicit send confirmation."""

import asyncio
import copy
from urllib.parse import parse_qs, urlparse

import pytest

from brain.catalog import Catalog
from brain.orchestrator import Orchestrator
from brain.tools import draft_email
from brain.traces import Tracer
from fakes import FakeServer


def run(coro):
    return asyncio.run(coro)


class FakePlanner:
    def __init__(self, text="Hello, thanks for reaching out."):
        self.text = text
        self.calls = []

    def generate(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        return self.text


class FakeWorker:
    async def submit_async(self, fn, *args, **kwargs):
        return fn(*args, **kwargs)


def make_orch(tmp_path, observe, **handlers):
    handlers.setdefault("observe", lambda _: observe)
    server = FakeServer(handlers=handlers)
    return Orchestrator(server, Catalog.load(), Tracer(tmp_path / "traces"))


def test_parse_request_and_negatives():
    assert draft_email.parse_request(
        "draft an email to my coworkers saying hello", {}) == {
            "to": "my coworkers", "about": "hello", "reply": False}
    assert draft_email.parse_request("help me reply to this email", {}) == {
        "to": None, "about": None, "reply": True}
    assert draft_email.parse_request(
        "email jordan that the report is ready", {}) is None
    assert draft_email.parse_request(
        "reply to mom's text", {"app": "Messages"}) is None


def test_postprocess_and_subject():
    assert draft_email.postprocess(
        '```text\nSubject: Hello\n"Hi there."\n[your name]\n```') == \
        "Hi there."
    assert draft_email.subject_for(
        "quarterly report details and next steps") == \
        "Quarterly report details and next steps"
    assert len(draft_email.postprocess("word " * 150).split()) <= 120


def test_mail_new_with_recipient_and_prompt(monkeypatch, tmp_path):
    obs = {"epoch": 1, "app": "Mail", "window": "Inbox", "elements": []}
    o = make_orch(tmp_path, obs, skill=lambda _: {"ok": True})
    model = FakePlanner('Subject: no\n"Hello there."\n[your name]')
    o.planner = model
    monkeypatch.setattr("brain.planner.worker", lambda: FakeWorker())
    monkeypatch.setattr(draft_email, "user_name", lambda: None)
    result = run(draft_email.run(
        o, {"to": "ada@example.com", "about": "hello"}, "draft an email"))
    assert result == "ok"
    call = next(params for method, params in o.server.rpcs
                if method == "skill")
    assert call["name"] == "compose_email"
    assert call["args"]["to"] == "ada@example.com"
    assert call["args"]["subject"] == "Hello"
    assert model.calls[0][0][0].endswith(
        "Do not sign the email and do not write any name or placeholder for "
        "the sender at the end.")
    assert model.calls[0][0][1] == (
        'Request: "draft an email"\nRecipient: ada@example.com\n'
        "Topic: hello\nMode: new email")
    assert o._draft["target"] == "mail"
    assert not any(params.get("combo") in ("cmd+return", "cmd+shift+d")
                   for method, params in o.server.rpcs if method == "act")


def test_mail_without_recipient_uses_escaped_applescript(
        monkeypatch, tmp_path):
    obs = {"epoch": 1, "app": "Mail", "window": "Inbox", "elements": []}
    o = make_orch(tmp_path, obs)
    o.planner = FakePlanner('He said "hello".')
    monkeypatch.setattr("brain.planner.worker", lambda: FakeWorker())
    monkeypatch.setattr(draft_email, "user_name", lambda: "")
    assert run(draft_email.run(o, {"about": "hello"},
                               "draft an email saying hello")) == "ok"
    code = next(params["code"] for method, params in o.server.rpcs
                if method == "act")
    assert 'content:"He said \\"hello\\"."' in code
    assert o.server.said[-1] == "Draft ready. Add recipients, then say send"


def test_gmail_fallback_prefills_url(monkeypatch, tmp_path):
    obs = {"epoch": 1, "app": "Google Chrome", "window": "Gmail",
           "elements": []}
    o = make_orch(tmp_path, obs, skill=lambda _: {"ok": True})
    o.planner = FakePlanner("Hello.")
    monkeypatch.setattr("brain.planner.worker", lambda: FakeWorker())
    monkeypatch.setattr(draft_email, "user_name", lambda: None)
    assert run(draft_email.run(
        o, {"to": "ada@example.com", "about": "status"},
        "draft an email in Gmail")) == "ok"
    params = next(p for m, p in o.server.rpcs if m == "skill")
    query = parse_qs(urlparse(params["args"]["url"]).query)
    assert query["to"] == ["ada@example.com"] and query["su"] == ["Status"]
    assert query["body"] == ["Hello."]


def test_gmail_compose_types_fields_without_send(monkeypatch, tmp_path):
    initial = {"epoch": 1, "app": "Chrome", "window": "Gmail",
               "elements": [
                   {"ref": 1, "role": "button", "label": "Compose"}]}
    fields = {"epoch": 2, "app": "Chrome", "window": "Gmail", "elements": [
        {"ref": 2, "role": "textfield", "label": "To recipients"},
        {"ref": 3, "role": "textfield", "label": "Subject"},
        {"ref": 4, "role": "textarea", "label": "Message body"}]}
    observations = iter([initial, fields, fields])
    o = make_orch(tmp_path, initial,
                  act=lambda _: {"ok": True})
    o.server.handlers["observe"] = lambda _: next(observations, {
        "epoch": 2, "app": "Chrome", "window": "Gmail", "elements": []})
    o.planner = FakePlanner("Hello.")
    monkeypatch.setattr("brain.planner.worker", lambda: FakeWorker())
    monkeypatch.setattr(draft_email, "user_name", lambda: None)
    assert run(draft_email.run(
        o, {"to": "ada@example.com", "about": "hello"},
        "draft an email in Gmail")) == "ok"
    typed = [p["ref"] for m, p in o.server.rpcs
             if m == "act" and p.get("op") == "type"]
    assert typed == [2, 3, 4]
    assert not any(p.get("combo") in ("cmd+return", "cmd+shift+d")
                   for m, p in o.server.rpcs if m == "act")


def test_mail_reply_uses_ocr_when_ax_context_is_short(monkeypatch, tmp_path):
    initial = {"epoch": 1, "app": "Mail", "window": "Inbox",
               "text": "From: Ada", "elements": []}
    reply = {"epoch": 2, "app": "Mail", "window": "Re: Hello",
             "focused_ref": 8, "elements": [
                 {"ref": 8, "role": "textarea", "label": "Message body"}]}
    observations = iter([reply, reply])
    o = make_orch(tmp_path, initial, act=lambda _: {"ok": True},
                  screenshot=lambda _: {"path": "shot.png"},
                  ocr=lambda _: {"text": "From: Ada\nSubject: Hello\n"
                                         "Thanks for writing."})
    o.server.handlers["observe"] = lambda _: next(observations, reply)
    model = FakePlanner("Thanks for your note.")
    o.planner = model
    monkeypatch.setattr("brain.planner.worker", lambda: FakeWorker())
    monkeypatch.setattr(draft_email, "user_name", lambda: None)
    assert run(draft_email.run(
        o, {"reply": True}, "help me reply to this email")) == "ok"
    assert model.calls[0][0][1].endswith(
        'Email on screen:\n"""\nFrom: Ada\nSubject: Hello\n'
        'Thanks for writing.\n"""')
    assert any(method == "screenshot" for method, _ in o.server.rpcs)
    assert any(params.get("combo") == "cmd+r" for method, params
               in o.server.rpcs if method == "act")
    assert any(params.get("op") == "type" and params.get("ref") == 8
               for method, params in o.server.rpcs if method == "act")


def test_no_model_signin_and_send_draft(monkeypatch, tmp_path):
    obs = {"epoch": 1, "app": "Chrome", "window": "Sign in - Gmail",
           "elements": []}
    o = make_orch(tmp_path, obs)
    assert run(draft_email.run(o, {}, "draft an email in Gmail")) == \
        "awaiting_user"
    assert o.server.said[-1] == "Please sign in to Gmail, then ask me again"

    o.planner = None
    obs["app"], obs["window"] = "Mail", "Inbox"
    o.server.handlers["observe"] = lambda _: obs
    assert run(draft_email.run(o, {}, "draft an email")) == "fallback"
    assert o.server.said[-1] == "Drafting isn't ready yet"

    o._draft = {"target": "mail", "app": "Mail", "window_title": "Inbox",
                "to": "ada@example.com", "reply": False, "t": 0}
    obs["elements"] = [
        {"ref": 1, "role": "textfield", "label": "To", "value": "ada@example.com"},
        {"ref": 2, "role": "textfield", "label": "Subject", "value": "Hello"}]
    o.server.confirm_yes = True
    o.server.handlers["act"] = lambda _: {"ok": True}
    assert run(draft_email.send_draft(o)) == "ok"
    assert o.server.rpcs[-1][1]["combo"] == "cmd+shift+d"
    assert o._draft is None


def test_send_draft_denied_and_precondition(monkeypatch, tmp_path):
    obs = {"epoch": 1, "app": "Mail", "window": "Inbox", "elements": []}
    o = make_orch(tmp_path, obs)
    o._draft = {"target": "mail", "app": "Mail", "window_title": "Inbox",
                "to": None, "reply": True, "t": 1}
    o.server.confirm_yes = False
    assert run(draft_email.send_draft(o)) == "cancelled"
    assert o._draft is None and "act" not in o.server.methods()
    o._draft = {"target": "mail", "app": "Mail", "window_title": "Other",
                "to": None, "reply": False, "t": 1}
    assert run(draft_email.send_draft(o)) == "failed"
    assert o.server.said[-1] == "The draft isn't in front anymore"


@pytest.mark.parametrize("target, app", [("mail", "Mail"), ("gmail", "Chrome")])
@pytest.mark.parametrize("change", ["none", "app", "window", "recipient", "subject",
                                    "body", "draft_ref", "missing", "error"])
def test_send_draft_rechecks_after_confirm(tmp_path, target, app, change):
    obs = {"epoch": 1, "app": app, "window": "Draft - Gmail" if target == "gmail" else "Hello",
           "elements": [
               {"ref": 1, "role": "textfield", "label": "To", "value": "ada@example.com"},
               {"ref": 2, "role": "textfield", "label": "Subject", "value": "Hello"},
               {"ref": 3, "role": "textarea", "label": "Message body", "value": "Hi Ada"}]}
    state = {"obs": obs}
    o = make_orch(tmp_path, obs, act=lambda _: {"ok": True})

    def observe(_):
        if state["obs"] == "error":
            raise RuntimeError("observe failed")
        return state["obs"]

    o.server.handlers["observe"] = observe
    o._draft = {"target": target, "app": app, "window_title": obs["window"],
                "to": "ada@example.com", "reply": False}

    async def confirm(summary):
        fresh = copy.deepcopy(obs)
        fresh["epoch"] = 2
        if change in ("app", "window"):
            fresh[change] = "Other"
        elif change in ("recipient", "subject", "body"):
            index = {"recipient": 0, "subject": 1, "body": 2}[change]
            fresh["elements"][index]["value"] = "Different"
        elif change == "draft_ref":
            fresh["elements"][2]["ref"] = 30
        state["obs"] = {} if change == "missing" else "error" if change == "error" else fresh
        return True

    o.server.ask_confirm = confirm
    assert run(draft_email.send_draft(o)) == ("ok" if change == "none" else "failed")
    acts = [p for method, p in o.server.rpcs if method == "act"]
    if change == "none":
        assert acts == [{"op": "keys", "combo": "cmd+shift+d" if target == "mail" else "cmd+return",
                         "epoch": 2}]
    else:
        assert not acts
    assert o._draft is None


def test_send_draft_unreadable_headers_never_sends(tmp_path):
    o = make_orch(tmp_path, {"app": "Mail", "window": "Hello", "elements": []})
    o._draft = {"target": "mail", "app": "Mail", "window_title": "Hello", "reply": True}
    assert run(draft_email.send_draft(o)) == "failed"
    assert "act" not in o.server.methods()


@pytest.mark.parametrize("text,about", [
    ("Reply to this email that I can be there in ten minutes",
     "I can be there in ten minutes"),
    ("reply saying I'll be there", "I'll be there"),
    ("reply that I'll be there", "I'll be there"),
    ("respond to this", None), ("answer this email", None),
    ("answer it", None)])
def test_reply_parsing(text, about):
    for ctx in ({"app": "Zen", "url": "https://mail.google.com/mail/u/0/"},
                {"app": "Mail"}):
        assert draft_email.parse_request(text, ctx) == {
            "to": None, "about": about, "reply": True}
    assert draft_email.parse_request("answer it", {"app": "Zen"}) is None


@pytest.mark.parametrize("host,suffix", [
    ("mail.google.com", ""), ("mail.google.com", " on gmail"),
    ("outlook.office.com", ""), ("app.fastmail.com", ""),
    ("custom.example", "")])
@pytest.mark.parametrize("role", ["textarea", "textbox", "textfield"])
def test_web_reply_in_place(monkeypatch, tmp_path, host, suffix, role):
    initial = {"epoch": 1, "app": "Zen", "window": "UC Berkeley Mail",
               "elements": [
                   {"ref": 1, "role": "link", "label": "Reply all"},
                   {"ref": 2, "role": "button", "label": "Reply"},
                   {"ref": 3, "role": "text", "label":
                    "From: Ada\nTo: me\nCan you meet in ten minutes?"}]}
    editor = {**initial, "epoch": 2, "focused_ref": 4, "elements": [
        *initial["elements"], {"ref": 4, "role": role,
                              "label": "" if role == "textfield" else "Message Body",
                              "value": ""}]}
    state = {"obs": initial}

    def act(params):
        if params["op"] == "press":
            state["obs"] = editor
        elif params["op"] == "type":
            editor["elements"][-1]["value"] = params["text"]
        return {"ok": True}

    o = make_orch(tmp_path, initial, act=act)
    o._ctx = {"app": "Zen"}
    o._focus_ctx = {"url": f"https://{host}/mail/u/0/#inbox/message",
                    "window_title": initial["window"]}
    o.server.handlers["observe"] = lambda _: state["obs"]
    o.planner = FakePlanner("I can be there in ten minutes.")
    monkeypatch.setattr("brain.planner.worker", lambda: FakeWorker())
    assert run(draft_email.run(o, {"reply": True},
        "Reply to this email that I can be there in ten minutes" + suffix)) == "ok"
    acts = [p for m, p in o.server.rpcs if m == "act"]
    assert acts == [{"op": "press", "ref": 2, "epoch": 1},
                    {"op": "type", "ref": 4, "epoch": 2,
                     "text": "I can be there in ten minutes."}]
    assert not any(m == "skill" or p.get("op") == "url" for m, p in o.server.rpcs)
    assert "Can you meet in ten minutes?" in o.planner.calls[0][0][1]
    assert o.server.said[-1] == "Draft ready. Say send to send it"
    assert run(draft_email.send_draft(o)) == "ok"
    assert o.server.confirms == ["Send the reply?"]
    assert o.server.rpcs[-1][1]["combo"] == "cmd+return"


@pytest.mark.parametrize("app,url", [("Zen", "https://mail.google.com/mail/u/0/#inbox"),
                                    ("Finder", "")])
def test_reply_without_open_message(tmp_path, app, url):
    o = make_orch(tmp_path, {"app": app, "window": "Inbox", "elements": []})
    o._ctx = {"app": app}
    o._focus_ctx = {"url": url}
    assert run(draft_email.run(o, {"reply": True}, "reply on gmail")) == "awaiting_user"
    assert o.server.said == ["Which email? Open it, then ask me again"]
    assert o.server.methods() == ["observe"]


def test_web_reply_body_changed_during_confirm(tmp_path):
    obs = {"app": "Zen", "window": "UC Berkeley Mail", "elements": [
        {"ref": 4, "role": "textbox", "label": "Message Body", "value": "Hello"}]}
    o = make_orch(tmp_path, obs)
    o._draft = {"target": "web", "reply": True, "app": "Zen",
                "window_title": obs["window"]}

    async def confirm(_):
        obs["elements"][0]["value"] = "Changed"
        return True

    o.server.ask_confirm = confirm
    assert run(draft_email.send_draft(o)) == "failed"
    assert o.server.said[-1] == "The draft changed; please check it again"
    assert "act" not in o.server.methods()


@pytest.mark.parametrize("failure", ["press", "editor", "type"])
def test_web_reply_failures(monkeypatch, tmp_path, failure):
    initial = {"epoch": 1, "app": "Zen", "window": "Mail", "elements": [
        {"ref": 2, "role": "button", "label": "Reply"},
        {"ref": 3, "role": "text", "label": "From: Ada: Can you meet soon?"}]}
    editor = {**initial, "epoch": 2, "elements": [
        {"ref": 4, "role": "textarea", "label": "Message body", "value": ""}]}
    state = {"obs": initial}

    def act(params):
        if params["op"] == failure:
            return {"ok": False, "error": "UI action failed"}
        if failure != "editor":
            state["obs"] = editor
        return {"ok": True}

    async def settle(_):
        pass

    o = make_orch(tmp_path, initial, act=act)
    o._ctx = {"app": "Zen"}
    o._focus_ctx = {"url": "https://mail.google.com/mail/u/0/#inbox/message"}
    o.server.handlers["observe"] = lambda _: state["obs"]
    o.planner = FakePlanner("Yes, soon.")
    monkeypatch.setattr("brain.planner.worker", lambda: FakeWorker())
    monkeypatch.setattr(draft_email.asyncio, "sleep", settle)
    assert run(draft_email.run(o, {"reply": True}, "reply saying yes")) == "failed"
    assert o._draft is None
    assert not any(m == "skill" or p.get("op") == "url" for m, p in o.server.rpcs)
    assert not any(p.get("combo") == "cmd+return" for _, p in o.server.rpcs)


@pytest.mark.parametrize("engine", [False, True])
@pytest.mark.parametrize("text", [
    "Reply to this email that I can be there in ten minutes",
    "reply saying I'll be there", "respond to this", "answer this email"])
def test_orchestrator_reply_redirect(monkeypatch, tmp_path, engine, text):
    from fakes import FakeEngine
    o = make_orch(tmp_path, {})
    o.engine = FakeEngine(default=("open_url", .99)) if engine else None
    o.route = lambda _: {"kind": "skill", "name": "open_url", "args": {}}
    calls = []

    async def tool(label, args, utterance):
        calls.append((label, args, utterance))
        return "ok"

    monkeypatch.setattr(o, "_brain_tool", tool)
    run(o.handle_utterance(text, {"app": "Zen",
        "url": "https://mail.google.com/mail/u/0/#inbox/FMfcg",
        "window_title": "hoke@berkeley.edu - UC Berkeley Mail"}))
    assert calls and calls[0][0] == "draft_email"
    assert calls[0][1]["reply"] is True
    assert not o.server.rpcs
    if engine:
        assert not o.engine.route_calls
