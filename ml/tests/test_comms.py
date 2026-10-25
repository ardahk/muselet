"""Messages-first resolution and safe send flow."""

import asyncio
import time

import pytest

from brain import comms, decision, planner, slots
from brain.comms import is_messaging, parse_message
from brain.catalog import Catalog
from brain.orchestrator import Orchestrator
from brain.traces import Tracer
from fakes import FakeEngine, FakeServer, _skill_rpcs


def run(coro):
    return asyncio.run(coro)


def contact(name, value, label="mobile", ident=None):
    return {"id": ident or name, "name": name, "handles": [{
        "kind": "phone", "value": value, "label": label}]}


def make_orch(tmp_path, matches=None, **handlers):
    mapped = {
        "messages_people": lambda _: {"people": []},
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


# ---------- parse_message / is_messaging (no orchestrator) ----------

@pytest.mark.parametrize("text,expected", [
    ("Send a message to Orda, Arda.", {"to": "Arda", "body": None}),
    ("Send a message to Arda.", {"to": "Arda", "body": None}),
    ("Send a text to Monica.", {"to": "Monica", "body": None}),
    ("Send a hello message to Arda.", {"to": "Arda", "body": "hello"}),
    ("Send a text message to Arda saying hello Arda",
     {"to": "Arda", "body": "hello Arda"}),
    ("Send a s text message to Caleb saying hello.",
     {"to": "Caleb", "body": "hello"}),
    ("Send a thank you message to mom",
     {"to": "mom", "body": "thank you"}),
    ("send a quick text to mom", {"to": "mom", "body": None}),
    ("shoot me a short message to Maya saying hi",
     {"to": "Maya", "body": "hi"}),
    ("drop an imessage to Sam that reads call me",
     {"to": "Sam", "body": "call me"}),
    ("send the sms to Pat: hello!", {"to": "Pat", "body": "hello!"}),
    ("send a note to arda saying hi", {"to": "arda", "body": "hi"}),
    ("send a note to my friend saying uh hello.",
     {"to": None, "body": "hello"}),
    ("send me a little text to him", {"to": None, "body": None}),
    ("send a brief note to someone that says hi",
     {"to": None, "body": "hi"}),
    ("send message to Arda", {"to": "Arda", "body": None}),
    ("send a message to Arda and say hello",
     {"to": "Arda", "body": "hello"}),
    ("send a message to Arda to say hello",
     {"to": "Arda", "body": "hello"}),
    ("send a message to Arda which says hello",
     {"to": "Arda", "body": "hello"}),
    ("send a message to Arda that hello", {"to": "Arda", "body": "hello"}),
    ("text her saying hi", {"to": None, "body": "hi"}),
    ("message them that says we are late",
     {"to": None, "body": "we are late"}),
    ("imessage to Arda", {"to": "Arda", "body": None}),
    ("sms Mom saying I'm outside", {"to": "Mom", "body": "I'm outside"}),
    ("text Arda hello", {"to": "Arda", "body": "hello"}),
    ("send Arda a text saying hi", {"to": "Arda", "body": "hi"}),
    ("shoot mom a message", {"to": "mom", "body": None}),
    ("drop Arda the text that says thanks", {"to": "Arda", "body": "thanks"}),
    ("send Mom a note to say hello", {"to": "Mom", "body": "hello"}),
    ("tell Mom I love you", {"to": "Mom", "body": "I love you"}),
    ("tell Mom that I love you", {"to": "Mom", "body": "I love you"}),
    ("tell my friend we are running late",
     {"to": None, "body": "we are running late"}),
    ("tell her hello", {"to": None, "body": "hello"}),
    ("tell me a joke", None),
    ("uh send a text to Arda", {"to": "Arda", "body": None}),
    ("um, send a text to Arda", {"to": "Arda", "body": None}),
    ("er send a text to Arda", {"to": "Arda", "body": None}),
    ("ah send a text to Arda", {"to": "Arda", "body": None}),
    ("hey, send a text to Arda", {"to": "Arda", "body": None}),
    ("okay send a text to Arda", {"to": "Arda", "body": None}),
    ("ok. send a text to Arda", {"to": "Arda", "body": None}),
    ("so send a text to Arda", {"to": "Arda", "body": None}),
    ("please send a text to Arda", {"to": "Arda", "body": None}),
    ("and send a text to Arda", {"to": "Arda", "body": None}),
    ("now send a text to Arda", {"to": "Arda", "body": None}),
    ("muselet send a text to Arda", {"to": "Arda", "body": None}),
    ("hey Muselet, please send a text to Arda",
     {"to": "Arda", "body": None}),
    ("can you send a text to Arda", {"to": "Arda", "body": None}),
    ("could you please text Arda", {"to": "Arda", "body": None}),
    ("would you send a message to Arda", {"to": "Arda", "body": None}),
    ("will you shoot a text to Arda", {"to": "Arda", "body": None}),
    ("I want you to send a text to Arda", {"to": "Arda", "body": None}),
    ("I need to send a message to Arda", {"to": "Arda", "body": None}),
    ("I'd like to text Arda", {"to": "Arda", "body": None}),
    ("I would like you to send a text to Arda",
     {"to": "Arda", "body": None}),
    ("let's send a message to Arda", {"to": "Arda", "body": None}),
    ("go ahead and send a text to Arda", {"to": "Arda", "body": None}),
    ("SEND A TEXT TO ARDA", {"to": "ARDA", "body": None}),
    ("send a message to orda i mean arda",
     {"to": "arda", "body": None}),
    ("send a message to Orda no Arda", {"to": "Arda", "body": None}),
    ("send a message to Orda sorry Arda", {"to": "Arda", "body": None}),
    ("send a message to Orda, Arda", {"to": "Arda", "body": None}),
    ("send a message to Arda, hi", {"to": "Arda", "body": "hi"}),
    ("send a message to Arda hi", {"to": "Arda", "body": "hi"}),
    ("send a message to Arda saying are you free?",
     {"to": "Arda", "body": "are you free?"}),
    ("send a message to Arda saying hello!",
     {"to": "Arda", "body": "hello!"}),
    ("text Arda saying “hello.”", {"to": "Arda", "body": "hello"}),
    ("send a message to Arda I love you",
     {"to": "Arda", "body": "I love you"}),
    ("send a hello message to Arda saying goodbye",
     {"to": "Arda", "body": "hello"}),
    ("send hello message to Arda", {"to": "Arda", "body": "hello"}),
    ("send a message to Arda Hoke saying hi",
     {"to": "Arda Hoke", "body": "hi"}),
    ("send a message to Arda please", {"to": "Arda", "body": None}),
    ("email arda saying hi", None),
    ("send an email to arda", None),
    ("open messages", None),
    ("type hello", None),
    ("what's the weather", None),
    ("set a timer for 5 minutes", None),
    ("draft an email to arda", None),
    ("write a note to self buy milk", None),
    ("note that the meeting is at 5", None),
    ("note to self buy milk", None),
    ("write a message to arda", None),
])
def test_parse_message(text, expected):
    assert parse_message(text) == expected


@pytest.mark.parametrize("text", [
    "text her", "texting Mom", "send messages to Mom", "iMessage Arda",
    "send an SMS", "texted Mom",
])
def test_is_messaging(text):
    assert is_messaging(text)


@pytest.mark.parametrize("text", [
    "email arda saying hi", "draft an email", "mail Monica", "gmail Arda",
])
def test_email_is_not_messaging(text):
    assert not is_messaging(text)


@pytest.mark.parametrize("text,want", [
    ("send a message saying hello to arda", {"to": "arda", "body": "hello"}),
    ("send a text saying i'll be late to arda hoke",
     {"to": "arda hoke", "body": "i'll be late"}),
    ("send a quick message saying on my way to mom",
     {"to": "mom", "body": "on my way"}),
    ("send her a quick text", {"to": None, "body": None}),
    ("send him a message saying hi", {"to": None, "body": "hi"}),
    ("tell john to call me", {"to": "john", "body": "call me"}),
    ("tell siri to call mom", None),
    ("tell my mac to sleep", None),
])
def test_lead_review_phrasings(text, want):
    assert parse_message(text) == want


@pytest.mark.parametrize("channel,canonical", [
    ("Slack", "slack"), ("Teams", "teams"), ("Microsoft Teams", "teams"),
    ("WhatsApp", "whatsapp"), ("Discord", "discord"), ("Telegram", "telegram"),
    ("Signal", "signal"), ("email", "email"), ("Google Chat", "chat"),
    ("Messages", "messages"), ("iMessage", "messages"),
])
@pytest.mark.parametrize("text", [
    "send a message to John on {channel} saying hi",
    "send a {channel} message to John saying hi",
    "text John saying hi via {channel}",
])
def test_brain38_parse_channel_separately_from_body(channel, canonical, text):
    text = text.format(channel=channel)
    assert parse_message(text) == {"to": "John", "body": "hi", "channel": canonical}
    assert is_messaging(text) == (canonical == "messages")


@pytest.mark.parametrize("text", [
    "tell Finder to empty the trash", "tell Spotify to play jazz",
    "tell TextEdit to save the file", "tell System Settings to open Bluetooth",
    "tell Google Chrome to close the tab", "text size bigger please",
    "text font smaller", "note buy milk", "",
])
def test_brain38_non_messaging_commands_are_not_contacts(text):
    assert parse_message(text) is None


def test_brain38_channel_without_body_and_body_mention():
    assert parse_message("send a message to John on Slack") == {
        "to": "John", "body": None, "channel": "slack"}
    assert parse_message("text John saying Slack is down") == {
        "to": "John", "body": "Slack is down"}


def test_messages_first_confirm_and_send_order(tmp_path):
    o = make_orch(tmp_path, [contact("Arda Hoke", "+15551234567")])
    trace = {"rpc": [], "stages": {}, "comms": []}
    o.tracer.current = trace
    assert run(comms.send_message(o, "arda", "hi")) == "ok"
    assert o.server.methods() == [
        "messages_people", "contacts_search", "messages_compose",
        "messages_send"]
    assert o.server.confirms == ["Send 'hi' to Arda Hoke (mobile)?"]
    assert o.server.rpcs[2][1] == {
        "handle": "+15551234567", "body": "hi", "name": "Arda Hoke"}
    assert trace["comms"][0]["resolve"]["source"] == "contacts"
    assert [next(iter(entry)) for entry in trace["comms"]] == [
        "resolve", "compose", "confirm", "send"]


def test_zero_matches_asks_for_real_handle(tmp_path):
    o = make_orch(tmp_path)
    assert run(comms.send_message(o, "arda", "hi")) == "awaiting_user"
    assert o.server.said[-1] == (
        "I couldn't find Arda in your contacts. What's their number or email?")
    assert o.server.methods() == [
        "messages_people", "contacts_search", "contacts_search"]


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
        {"send a text to mom saying hi": ("send_message", 0.95)},
        {("send_message", "send a text to mom saying hi"):
         {"to": "Mom", "body": "hi"}})
    assert run(o.handle_utterance(
        "send a text to mom saying hi"))["outcome"] == "ok"
    assert o.server.methods() == [
        "messages_people", "contacts_search", "messages_compose",
        "messages_send"]

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


@pytest.mark.parametrize("error,message", [
    ("recipient_unverified",
     "Couldn't confirm that conversation, so I stopped"),
    ("no_text_target", "Couldn't find the Messages text box"),
    ("bad_handle", "That number or email doesn't look right"),
    ("screen_locked", "Unlock your screen first"),
    ("not_frontmost", "Messages didn't come to the front"),
])
def test_compose_error_bubbles(tmp_path, error, message):
    def boom(_):
        raise RuntimeError(error)
    o = make_orch(tmp_path, [contact("Mom", "+15551234567")],
                  messages_compose=boom)
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
    assert "draft_email" not in {name for name, _ in options}
    assert "draft_email(" in planner.catalog_desc(catalog, lambda _: "")


def test_compound_classifies_send_message_as_nonfast_path(tmp_path):
    o = make_orch(tmp_path)
    o.engine = FakeEngine({"a": ("send_message", 0.9),
                           "b": ("mute", 0.9)})
    trace = {"decisions": []}
    assert run(o._compound("a then b", trace)) is None


def test_message_parser_precedes_compound_routing(tmp_path):
    text = "text mom I love you and miss you"
    eng = FakeEngine(
        routes={"text mom i love you": ("send_message", 0.9),
                "miss you": ("send_message", 0.8),
                text.lower(): ("send_message", 0.95)},
        argmap={("send_message", text.lower()):
                {"to": "Mom", "body": "I love you and miss you"}})
    srv = FakeServer()
    o = Orchestrator(srv, Catalog.load(), Tracer(tmp_path / "t"), engine=eng)
    result = run(o.handle_utterance(text))
    assert result["outcome"] == "awaiting_user"
    assert eng.route_calls == []
    assert not _skill_rpcs(srv)
    assert srv.methods() == [
        "messages_people", "contacts_search", "contacts_search"]

def test_stt_correction_and_missing_body_restart(tmp_path):
    o = make_orch(tmp_path, [contact("Arda Hoke", "+15551234567")])
    first = run(o.handle_utterance("Send a message to Orda, Arda."))
    assert first["outcome"] == "awaiting_user"
    assert o.server.said[-1] == "What should the message to Arda say?"
    assert o.server.methods() == []

    assert run(o.handle_utterance("hi"))["outcome"] == "ok"
    assert o.server.methods() == [
        "messages_people", "contacts_search", "messages_compose",
        "messages_send"]
    assert o.server.rpcs[0][1] == {"query": "Arda", "limit": 5}
    assert o.server.rpcs[2][1] == {
        "handle": "+15551234567", "body": "hi", "name": "Arda Hoke"}


def test_s_stray_letter_and_resolved_name_for_compose(tmp_path):
    o = make_orch(tmp_path, [contact("Caleb Kawano", "+15551234567")])
    text = "Send a s text message to Caleb saying hello."
    assert run(o.handle_utterance(text))["outcome"] == "ok"
    assert o.server.methods() == [
        "messages_people", "contacts_search", "messages_compose",
        "messages_send"]
    assert o.server.rpcs[2][1] == {
        "handle": "+15551234567", "body": "hello", "name": "Caleb Kawano"}


def test_new_message_restarts_while_waiting_for_handle(tmp_path):
    def lookup(params):
        return {"matches": [contact("Arda Hoke", "+15551234567")]
                if params["query"] == "Arda" else []}

    o = make_orch(tmp_path, contacts_search=lookup)
    assert run(comms.send_message(o, "Orda", "hello")) == "awaiting_user"
    assert o._comms["kind"] == "handle"
    assert run(o.handle_utterance("Send a message to Arda."))[
        "outcome"] == "awaiting_user"
    assert o._comms["kind"] == "body"
    assert o.server.said[-1] == "What should the message to Arda say?"

    assert run(o.handle_utterance("hi"))["outcome"] == "ok"
    queries = [params["query"] for method, params in o.server.rpcs
               if method in ("messages_people", "contacts_search")]
    assert queries == ["Orda", "Orda", "Orda", "Arda", "Arda"]
    assert o.server.methods()[-3:] == [
        "contacts_search", "messages_compose", "messages_send"]


def test_pronoun_recipient_asks_without_search(tmp_path):
    o = make_orch(tmp_path, [contact("Arda", "+15551234567")])
    assert run(o.handle_utterance("text her saying hi"))[
        "outcome"] == "awaiting_user"
    assert o.server.said[-1] == "Who should I text?"
    assert o.server.methods() == []
    assert run(o.handle_utterance("Arda"))["outcome"] == "ok"
    assert o.server.rpcs[0][1] == {"query": "Arda", "limit": 5}
    assert o.server.rpcs[2][1]["body"] == "hi"


def test_body_answer_say_hello_never_routes_to_typing(tmp_path):
    o = make_orch(tmp_path, [contact("Monica", "+15551234567")])
    o.engine = FakeEngine({"say hello.": ("type_text", 0.95)})
    assert run(o.handle_utterance("Send a text to Monica."))[
        "outcome"] == "awaiting_user"
    assert o.server.said[-1] == "What should the message to Monica say?"
    assert run(o.handle_utterance("Say hello."))["outcome"] == "ok"
    assert o.server.methods() == [
        "messages_people", "contacts_search", "messages_compose",
        "messages_send"]
    assert o.server.rpcs[2][1]["body"] == "hello"


def test_engine_ask_messaging_uses_comms_args(tmp_path):
    text = "Send a text to Monica."
    o = make_orch(tmp_path)
    o.engine = FakeEngine(
        argmap={("send_message", text.lower()): {"to": "Monica"}})
    trace = {"decisions": [], "rpc": [], "stages": {}}
    assert run(o._engine_ask(text, trace, [("ASK", 0.89)])) == \
        "awaiting_user"
    assert o.server.said[-1] == "What should the message to Monica say?"
    assert o.engine.args_calls == [("send_message", text)]
    assert o.server.methods() == []


def test_engine_compose_email_route_is_rewritten_for_messages(tmp_path):
    text = "Send a hello message to Arda."
    o = make_orch(tmp_path, [contact("Arda", "+15551234567")])
    o.engine = FakeEngine(
        {text.lower(): ("compose_email", 0.9)},
        {("send_message", text.lower()): {
            "to": "Arda", "body": "hello"}})
    trace = {"decisions": [], "rpc": [], "stages": {}}
    o.tracer.current = trace
    assert run(o._engine_route(text, trace)) == "ok"
    assert o.engine.args_calls == [("send_message", text)]
    assert any(call == {"channel_fix": ["compose_email", "send_message"]}
               for call in trace["decisions"])
    assert o.server.methods() == [
        "messages_people", "contacts_search", "messages_compose",
        "messages_send"]
    assert o.server.rpcs[2][1] == {
        "handle": "+15551234567", "body": "hello", "name": "Arda"}


def test_email_request_remains_on_email_channel(tmp_path):
    text = "email arda saying hi"
    o = make_orch(tmp_path)
    o.engine = FakeEngine(
        {text: ("compose_email", 0.95)},
        {("compose_email", text): {"to": "Arda", "body": "hi"}})
    assert comms.parse_message(text) is None
    assert run(o.handle_utterance(text))["outcome"] == "ok"
    assert o.server.methods() == ["skill"]
    assert o.server.skills()[0]["name"] == "compose_email"


@pytest.mark.parametrize("text", [
    "send a message to John on Slack", "send whatsapp message to ali saying hi",
    "send a message to John on Teams saying hi", "text John via Discord saying hi",
    "send a message to John via email saying hi",
    "tell Finder to empty the trash", "tell Spotify to play jazz",
    "text size bigger please", "note buy milk",
])
def test_brain38_bypasses_contacts_and_reaches_router(tmp_path, text):
    o = make_orch(tmp_path, [contact("John", "+15551234567")])
    o.engine = FakeEngine()
    routed = []

    async def route(text, trace):
        routed.append(text)
        return "routed"

    o._engine_route = route
    assert run(o.handle_utterance(text))["outcome"] == "routed"
    assert routed == [text]
    assert o.server.methods() == []


@pytest.mark.parametrize("text", [
    "text John saying hi", "send a message to John saying hi",
    "send a message to John on Messages saying hi",
])
def test_brain38_native_messages_keep_contacts_first(tmp_path, text):
    o = make_orch(tmp_path, [contact("John", "+15551234567")])
    o.engine = FakeEngine()
    assert run(o.handle_utterance(text))["outcome"] == "ok"
    assert o.engine.route_calls == []
    assert o.server.methods() == [
        "messages_people", "contacts_search", "messages_compose", "messages_send"]
    assert o.server.rpcs[2][1]["body"] == "hi"
    assert len(o.server.confirms) == 1


@pytest.mark.parametrize("pending", [None, "slot", "comms"])
def test_brain38_foreign_channel_never_composes_from_shared_entry(tmp_path, pending):
    text = "send a message to John on Slack saying hi"
    o = make_orch(tmp_path, [contact("John", "+15551234567")])
    o.engine = FakeEngine({text.lower(): ("send_message", 0.95)}, {
        ("send_message", text.lower()): {"to": "John", "body": "hi"}})
    if pending == "slot":
        o._slot = {"skill": "open_app", "args": {}, "missing": ["app"], "t": time.time()}
    elif pending == "comms":
        o._comms = {"kind": "body", "to": "John", "t": time.time()}
    planned = []

    async def plan(text, trace):
        planned.append(text)
        return "planned"

    o._planner_loop = plan
    assert run(o.handle_utterance(text))["outcome"] == "planned"
    assert planned == [text]
    assert o.server.methods() == []


@pytest.mark.parametrize("answer", ["Ardaoke.", "Arda okay."])
def test_whole_name_fuzzy_disambiguation(tmp_path, answer):
    contacts = [
        contact("Arda Didim", "+15550000001", ident="didim"),
        contact("Arda Hoke", "+15550000002", ident="hoke"),
        contact("H Arda", "+15550000003", ident="h-arda"),
        contact("Arda Long", "+15550000004", ident="long"),
        contact("Arda New", "+15550000005", ident="new"),
    ]
    o = make_orch(tmp_path, contacts)
    assert run(comms.send_message(
        o, "Arda", "hello")) == "awaiting_user"
    assert o.server.said[-1] == \
        "Arda Didim, Arda Hoke, or H Arda?"
    assert run(o.handle_utterance(answer))["outcome"] == "ok"
    assert o.server.rpcs[-2][1] == {
        "handle": "+15550000002", "body": "hello", "name": "Arda Hoke"}


def test_fuzzy_name_near_tie_stays_ambiguous():
    opts = comms.options([
        contact("Arda Hoke", "+15550000001", ident="one"),
        contact("Arda Hoka", "+15550000002", ident="two"),
    ])
    assert comms.resolve_answer("ardahok", opts) == (None, None)


def test_single_messages_person_skips_contacts(tmp_path):
    person = {"name": "Arda Hoke", "handles": [{
        "kind": "phone", "value": "+15551234567"}], "chat": True}
    o = make_orch(
        tmp_path, [contact("Arda Hoke", "+15551234567"),
                   contact("Arda Didim", "+15551234568")],
        messages_people=lambda _: {"people": [person]})
    trace = {"rpc": [], "stages": {}, "comms": []}
    o.tracer.current = trace
    assert run(comms.send_message(o, "Arda", "hi")) == "ok"
    assert o.server.methods() == ["messages_people", "messages_compose",
                                  "messages_send"]
    assert o.server.rpcs[1][1] == {
        "handle": "+15551234567", "body": "hi", "name": "Arda Hoke"}
    assert trace["comms"][0]["resolve"]["source"] == "messages"
    assert trace["comms"][0]["resolve"]["n_people"] == 1


def test_messages_and_contacts_deduplicate_and_trace_both(tmp_path):
    people = [
        {"name": "Arda Hoke", "handles": [{
            "kind": "phone", "value": "+1 (555) 000-0001"}], "chat": True},
        {"name": "Arda Didim", "handles": [{
            "kind": "phone", "value": "+15550000003"}], "chat": True},
    ]
    contacts = [
        contact("Arda Hoke", "+15550000001", ident="duplicate"),
        contact("Arda Smith", "+15550000002", ident="smith"),
    ]
    o = make_orch(tmp_path, contacts,
                  messages_people=lambda _: {"people": people})
    trace = {"rpc": [], "stages": {}, "comms": []}
    o.tracer.current = trace
    assert run(comms.send_message(o, "Arda", "hi")) == "awaiting_user"
    event = trace["comms"][0]["resolve"]
    assert event["source"] == "both"
    assert event["n_matches"] == 3
    assert event["n_people"] == 2
    assert o.server.said[-1] == "Arda Hoke, Arda Didim, or Arda Smith?"


@pytest.mark.parametrize("mode", ["raise", "ok_false", "timeout"])
def test_messages_people_errors_fall_back_silently(tmp_path, mode):
    if mode in ("raise", "timeout"):
        error = "unknown method" if mode == "raise" else "timeout"

        def people_error(_):
            raise RuntimeError(error)
    else:
        def people_error(_):
            return {"ok": False, "error": "messages_automation_denied"}
    o = make_orch(
        tmp_path, [contact("Mom", "+15551234567")],
        messages_people=people_error)
    assert run(comms.send_message(o, "Mom", "hi")) == "ok"
    assert o.server.methods() == [
        "messages_people", "contacts_search", "messages_compose",
        "messages_send"]
    assert o.server.said == ["Sent to Mom"]


def test_messages_people_uses_four_second_timeout(tmp_path):
    class TimedServer(FakeServer):
        def __init__(self, handlers):
            super().__init__(handlers=handlers)
            self.timeouts = {}

        async def rpc(self, method, params, timeout=30):
            self.timeouts[method] = timeout
            return await super().rpc(method, params, timeout)

    server = TimedServer({
        "messages_people": lambda _: {"people": []},
        "contacts_search": lambda _: {
            "matches": [contact("Mom", "+15551234567")]},
        "messages_compose": lambda _: {
            "ok": True, "frontmost": True, "body_visible": True},
        "messages_send": lambda _: {"ok": True, "sent": True},
    })
    o = Orchestrator(server, Catalog.load(), Tracer(tmp_path / "traces"))
    assert run(comms.send_message(o, "Mom", "hi")) == "ok"
    assert server.timeouts["messages_people"] == 4


def test_fuzzy_fallback_yes_and_no(tmp_path):
    def lookup(params):
        if params.get("fuzzy"):
            return {"matches": [{
                **contact("Arda Hoke", "+15551234567"),
                "score": 0.9}]}
        return {"matches": []}

    o = make_orch(tmp_path, contacts_search=lookup)
    assert run(comms.send_message(o, "Arda", "hi")) == "awaiting_user"
    assert o.server.said[-1] == "Did you mean Arda Hoke?"
    assert o.server.rpcs[2][1] == {
        "query": "Arda", "limit": 5, "fuzzy": True}
    assert run(o.handle_utterance("yes"))["outcome"] == "ok"
    assert o.server.rpcs[-2][1] == {
        "handle": "+15551234567", "body": "hi", "name": "Arda Hoke"}

    o2 = make_orch(tmp_path / "no", contacts_search=lookup)
    assert run(comms.send_message(o2, "Arda", "hi")) == "awaiting_user"
    assert run(o2.handle_utterance("no"))["outcome"] == "awaiting_user"
    assert o2._comms["kind"] == "handle"
    assert o2.server.said[-1] == "What's their number or email?"


def test_fuzzy_fallback_empty_and_multiple_candidates(tmp_path):
    candidates = [
        {**contact("Arda Didim", "+15550000002"), "score": 0.7},
        {**contact("Arda Hoke", "+15550000001"), "score": 0.9},
    ]

    def lookup(params):
        return {"matches": candidates if params.get("fuzzy") else []}

    o = make_orch(tmp_path, contacts_search=lookup)
    assert run(comms.send_message(o, "Arda", "hi")) == "awaiting_user"
    assert o.server.said[-1] == "Arda Hoke or Arda Didim?"

    empty = make_orch(tmp_path / "empty")
    assert run(comms.send_message(empty, "Arda", "hi")) == "awaiting_user"
    assert empty._comms["kind"] == "handle"
    assert empty.server.said[-1] == (
        "I couldn't find Arda in your contacts. What's their number or email?")


@pytest.mark.parametrize("op", [
    {"op": "open", "app": "Mail"},
    {"op": "skill", "name": "open_app", "args": {"app": "Mail"}},
])
def test_planner_mail_open_is_terminal_for_message_goal(tmp_path, op):
    o = make_orch(tmp_path)
    o._current_goal = "send a message to Mom saying hi"
    result = run(o._exec_action(op))
    assert result["status"] == "failed"
    assert result["_terminal_failure"] is True
    assert o.server.said[-1] == "I text through Messages, not Mail"
    assert o.server.methods() == []


def test_planner_compose_email_rewrites_to_message(tmp_path):
    o = make_orch(tmp_path, [contact("Mom", "+15551234567")])
    o._current_goal = "send a text to Mom saying hi"
    trace = {"decisions": [], "rpc": [], "stages": {}}
    o.tracer.current = trace
    result = run(o._exec_action({
        "op": "skill", "name": "compose_email",
        "args": {"to": "Mom", "body": "hi"}}))
    assert result["status"] == "ok"
    assert any(item == {"channel_fix": ["compose_email", "send_message"]}
               for item in trace["decisions"])
    assert o.server.methods() == [
        "messages_people", "contacts_search", "messages_compose",
        "messages_send"]
    assert not o.server.skills()
