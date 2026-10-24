"""Draft-email parsing, composition, and explicit send confirmation."""

import asyncio
from urllib.parse import parse_qs, urlparse

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
