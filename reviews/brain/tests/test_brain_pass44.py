"""brain review pass 44 repros. Run from repo root:
PYTHONPATH=ml/src:ml/tests pytest reviews/brain/tests/test_brain_pass44.py
(mlx can be stubbed; only the static parser is exercised)."""
import inspect
import re

from brain.decision import DecisionEngine


def test_brain41_truncated_args_line_is_not_accepted_as_complete():
    # 24-token decode cap: a 19-word body renders to 25 tokens (Qwen3.5-4B
    # tokenizer), so the closing quote is never generated.
    cut = 'to=Sarah body="Running ten minutes late, start the meeting without'
    got = DecisionEngine._parse_args_line(cut, {"to", "body"})
    # an unterminated quote means the decode was cut; the value must not be
    # delivered as the full body (should surface truncation / ASK / re-decode)
    assert "body" not in got or got.get("truncated"), got


def test_brain41_args_decode_budget_covers_free_text():
    src = inspect.getsource(DecisionEngine.args)
    cap = int(re.search(r"for _ in range\((\d+)\)", src).group(1))
    # 20-word dictation -> 26 tokens, subject+body email -> 29 tokens
    assert cap >= 64, cap
