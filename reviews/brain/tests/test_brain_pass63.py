"""brain-47: _CALL_PERSON now accepts a 1-word value, so call requests become 'remember' commands."""
import pytest
from brain.memory.policy import memory_command


@pytest.mark.parametrize("text", ["call my dad back", "call my mom now",
                                  "call me back later"])
def test_call_request_is_not_a_memory_write(text):
    assert memory_command(text) is None, memory_command(text)
