from types import SimpleNamespace

from brain.memory.policy import (
    allowed_value, extract_writes, forget_command, memory_command,
    planner_writes,
)


def test_privacy_filter_rejects_codes_and_secret_phrases():
    assert not allowed_value("my bank pin is 4821")
    assert not allowed_value("the code is 123456")
    assert not allowed_value("use password for login")
    assert not allowed_value("card 4111 1111 1111 1111")
    assert not allowed_value("remember this message body")
    assert allowed_value("I like green tea")


def test_fact_preference_and_person_write_commands():
    fact = memory_command("Remember that I drink green tea every morning")
    assert fact.write == {
        "type": "fact", "key": "drink green tea every morning",
        "value": "I drink green tea every morning"}
    assert fact.reply == "Got it, I'll remember that."

    assert memory_command("my favorite color is blue").write == {
        "type": "preference", "key": "color", "value": "blue"}
    assert memory_command("I prefer dark roast for coffee").write == {
        "type": "preference", "key": "coffee", "value": "dark roast"}
    assert memory_command("my mom is Jane Kim").write == {
        "type": "person", "key": "mom", "value": "Jane Kim"}
    assert memory_command("call Mom Jane Kim").write == {
        "type": "person", "key": "mom", "value": "Jane Kim"}
    assert memory_command("remember my pin is 4821") is None


def test_correction_requires_a_short_previous_argument():
    previous = SimpleNamespace(args={"query": "Kayla"})
    assert extract_writes(
        "no, I meant Caleb", previous_turn=previous) == [{
            "type": "correction", "key": "kayla", "value": "Caleb"}]
    assert extract_writes(
        "I meant Caleb", previous_turn=previous) == [{
            "type": "correction", "key": "kayla", "value": "Caleb"}]
    assert extract_writes(
        "no, I meant Caleb", previous_turn=SimpleNamespace(
            args={"query": "the very long contact name"})) == []


def test_forget_commands_and_planner_writes():
    assert forget_command("forget that") == ("that", None)
    assert forget_command("forget about Mom") == ("query", "mom")
    assert forget_command("forget everything") == ("clear", None)
    assert forget_command("what do you remember about tea") == (
        "remember", "tea")
    writes = planner_writes("make a folder", "Finder", 2)
    assert [(row["type"], row["key"]) for row in writes] == [
        ("episode", "make folder"), ("workflow", "make folder")]
    assert extract_writes(
        "send a message saying SECRET BODY", skill="send_message",
        args={"body": "SECRET BODY"}) == []
