"""Contacts-first Messages safety flow."""

import asyncio
import time

import pytest

from brain import comms, decision, planner, slots
from brain.catalog import Catalog
from brain.orchestrator import Orchestrator
from brain.traces import Tracer
from fakes import FakeEngine, FakeServer


def run(coro):
    return asyncio.run(coro)


def contact(name, value, label="mobile", ident=None):
    return {"id": ident or name, "name": name, "handles": [{
        "kind": "phone", "value": value, "label": label}]}


def make_orch(tmp_path, matches=None, **handlers):
    mapped = {
        "contacts_search": lambda _: {"matches": matches or []},
        "messages_compose": lambda _: {
            "ok": True, "frontmost": True, "body_visible": True},
        "messages_send": lambda _: {"ok": True, "sent": True},
    }
    mapped.update(handlers)
    server = FakeServer(handlers=mapped)
    return Orchestrator(server, Catalog.load(), Tracer(tmp_path / "traces"))


@pytest.mark.parametrize("text,expected", [
    ("+1 (555) 123-4567", {"kind": "phone", "value": "+15551234567",
                           "label": ""}),
    ("ardA@example.COM", {"kind": "email", "value": "arda@example.com",
                          "label": ""}),
    ("Arda", None), ("123-45", None),
])
def test_verbatim_handle(text, expected):
    assert comms.verbatim_handle(text) == expected


def test_spoken_email_and_clean_query():
    assert comms.spoken_email("arda at gmail dot com") == {
        "kind": "email", "value": "arda@gmail.com", "label": ""}
    assert comms.clean_query("to my Arda's,") == "Arda"


def test_rank_options_display_and_question():
    hoke = contact("Arda Hoke", "+15550000001")
    smith = contact("Arda Smith", "+15550000002")
    ranked = comms.rank(
        "arda", [hoke, smith, contact("Martha", "+15550000003")])
    opts = comms.options(ranked)
    assert [o["name"] for o in opts] == ["Arda Hoke", "Arda Smith"]
    assert comms.question(opts) == "Arda Hoke or Arda Smith?"
    many = comms.options([{
        "id": "a", "name": "Arda Hoke", "handles": [
            {"kind": "phone", "value": "1111111", "label": "home"},
            {"kind": "phone", "value": "2222222",
             "label": "_$!<Mobile>!$_"},
            {"kind": "email", "value": "a@b.com", "label": ""}]}])
    assert [o["handle"]["label"] for o in many] == ["mobile", "home", "email"]
    assert comms.display(many[0], many) == "Arda Hoke (mobile)"
    assert comms.resolve_answer("the mobile", many) == (0, "label")
    assert comms.resolve_answer("2222", many) == (0, "digits")


def test_contacts_first_confirm_and_send_order(tmp_path):
    o = make_orch(tmp_path, [contact("Arda Hoke", "+15551234567")])
    trace = {"rpc": [], "stages": {}, "comms": []}
    o.tracer.current = trace
    assert run(comms.send_message(o, "arda", "hi")) == "ok"
    assert o.server.methods() == [
        "contacts_search", "messages_compose", "messages_send"]
    assert o.server.confirms == ["Send 'hi' to Arda Hoke (mobile)?"]
    assert o.server.rpcs[1][1] == {"handle": "+15551234567", "body": "hi"}
    assert [next(iter(entry)) for entry in trace["comms"]] == [
        "resolve", "compose", "confirm", "send"]


def test_zero_matches_asks_for_real_handle(tmp_path):
    o = make_orch(tmp_path)
    assert run(comms.send_message(o, "arda", "hi")) == "awaiting_user"
    assert o.server.said[-1] == (
        "I couldn't find Arda in your contacts. What's their number or email?")
    assert o.server.methods() == ["contacts_search"]


@pytest.mark.parametrize(
    "answer", ["the second one", "first", "Smith", "5552"])
def test_disambiguation_answers(tmp_path, answer):
    o = make_orch(tmp_path, [
        contact("Arda Hoke", "+15550005551", ident="h"),
        contact("Arda Smith", "+15550005552", label="home", ident="s")])
    assert run(comms.send_message(o, "Arda", "hi")) == "awaiting_user"
    assert o.server.said[-1] == "Arda Hoke or Arda Smith?"
    result = run(o.handle_utterance(answer))
    assert result["outcome"] == "ok"
    assert o.server.methods()[-2] == "messages_compose"


@pytest.mark.parametrize("answer", ["415 555 1234", "ada at example dot com"])
def test_handle_answer_after_zero_matches(tmp_path, answer):
    def lookup(params):
        return {"matches": [] if params["query"] == "unknown" else [
            contact("Ada", "+14155551234")]}
    o = make_orch(tmp_path, contacts_search=lookup)
    run(comms.send_message(o, "unknown", "hi"))
    assert run(o.handle_utterance(answer))["outcome"] == "ok"
    assert o.server.methods()[-2] == "messages_compose"


@pytest.mark.parametrize("timeout", [False, True])
def test_no_or_timeout_leaves_draft(tmp_path, timeout):
    o = make_orch(tmp_path, [contact("Mom", "+15551234567")])
    o.server.confirm_yes = False
    o.server.confirm_raises = timeout
    assert run(comms.send_message(o, "Mom", "hi")) == "cancelled"
    assert o.server.said[-1] == "Left it as a draft"
    assert "messages_send" not in o.server.methods()


def test_cancel_pending_and_expire_ttl(tmp_path):
    o = make_orch(tmp_path, [
        contact("Arda Hoke", "+15550005551"),
        contact("Arda Smith", "+15550005552", label="home")])
    assert run(comms.send_message(o, "Arda", "hi")) == "awaiting_user"
    assert run(o.handle_utterance("cancel"))["outcome"] == "cancelled"
    assert o._comms is None and "messages_send" not in o.server.methods()

    o._comms = {"kind": "choose", "to": "Arda", "body": "hi", "opts": [],
                "t": time.time() - slots.SLOT_TTL_S - 1, "tries": 0,
                "from_planner": False}
    run(o.handle_utterance("unrelated"))
    assert o._comms is None


def test_superseding_command_routes_out_of_disambiguation(tmp_path):
    o = make_orch(tmp_path, [
        contact("Arda Hoke", "+15550005551"),
        contact("Arda Smith", "+15550005552", label="home")])
    o.engine = FakeEngine({"mute": ("mute", 0.95)})
    assert run(comms.send_message(o, "Arda", "hi")) == "awaiting_user"
    run(o.handle_utterance("mute"))
    assert o._comms is None
    assert any(params.get("name") == "mute" for params in o.server.skills())


def test_routed_send_and_send_failure(tmp_path):
    o = make_orch(tmp_path, [contact("Mom", "+15551234567")])
    o.engine = FakeEngine(
        {"send a text to mom": ("send_message", 0.95)},
        {("send_message", "send a text to mom"):
         {"to": "Mom", "body": "hi"}})
    assert run(o.handle_utterance("send a text to mom"))["outcome"] == "ok"
    assert o.server.methods() == [
        "contacts_search", "messages_compose", "messages_send"]

    failed = make_orch(
        tmp_path, [contact("Mom", "+15551234567")],
        messages_send=lambda _: {"ok": True, "sent": False})
    assert run(comms.send_message(failed, "Mom", "hi")) == "failed"
    assert failed.server.said[-1] == "Message didn't send"


def test_verbatim_email_skips_contacts(tmp_path):
    o = make_orch(tmp_path)
    assert run(comms.send_message(o, "ARDa@example.com", "hi")) == "ok"
    assert o.server.methods() == ["messages_compose", "messages_send"]
    assert o.server.rpcs[0][1]["handle"] == "arda@example.com"


@pytest.mark.parametrize("error,result,message", [
    ("contacts_denied", None, "Allow Contacts for Muselet in System Settings"),
    (None, {"ok": True, "frontmost": False},
     "Messages didn't come to the front"),
    (None, {"ok": True, "frontmost": True, "body_visible": False},
     "Couldn't put the text in Messages"),
])
def test_errors_fail_closed(tmp_path, error, result, message):
    handlers = {}
    if error:
        def denied(_):
            raise RuntimeError(error)
        handlers["contacts_search"] = denied
    else:
        handlers["messages_compose"] = lambda _: result
    o = make_orch(tmp_path, [contact("Mom", "+15551234567")], **handlers)
    assert run(comms.send_message(o, "Mom", "hi")) == "failed"
    assert o.server.said[-1] == message
    assert not o.server.confirms


def test_planner_send_consumes_confirm_and_terminal_failure(tmp_path):
    o = make_orch(tmp_path, [contact("Mom", "+15551234567")],
                  messages_compose=lambda _: {
                      "ok": False, "error": "not_frontmost"})
    o._batch_confirmed = True
    result = run(o._exec_action({
        "op": "skill", "name": "send_message",
        "args": {"to": "Mom", "body": "hi"}}))
    assert result["status"] == "failed"
    assert result["_terminal_failure"] is True
    assert not o._batch_confirmed and not o.server.skills()


def test_router_hides_draft_but_planner_keeps_it():
    catalog = Catalog.load()
    options = decision.catalog_options(catalog)
    hidden = {name for name, spec in catalog.skills.items()
              if spec.get("router") is False}
    assert "draft_email" not in {name for name, _ in options}
    assert [name for name, _ in options] == [
        name for name in catalog.skills if name not in hidden] + [
            item["name"] for item in catalog.special_options]
    assert "draft_email(" in planner.catalog_desc(catalog, lambda _: "")


def test_compound_classifies_send_message_as_nonfast_path(tmp_path):
    o = make_orch(tmp_path)
    o.engine = FakeEngine({"a": ("send_message", 0.9),
                           "b": ("mute", 0.9)})
    trace = {"decisions": []}
    assert run(o._compound("a then b", trace)) is None
