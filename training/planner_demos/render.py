"""Planner prompts exactly as the runtime builds them (ml/src/brain/planner.py), without the few-shot block.

system = planner_prompt(catalog_desc(Catalog.load(), DecisionEngine.arg_signature))   (prompts/planner_system.md)
user   = Planner.user_message(goal, observation, history(last_batch, "dsl"), hint=None, script_output, login_page)
login_page uses the orchestrator's regex over window + observation text. brain.planner imports MLX at module level;
on Linux every missing third-party import (mlx, numpy, torch, tinker, ...) is stubbed; none is used by these functions.
"""

from __future__ import annotations

import re
import sys
import types
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parents[2]
LOGIN_RE = re.compile(r"\b(?:sign\s*in|sign-in|log\s*in|login|password)\b", re.IGNORECASE)  # orchestrator.py


def _stub(name: str) -> None:
    m = types.ModuleType(name)
    m.__path__ = []
    m.__getattr__ = lambda attr, _n=name: mock.MagicMock(name=f"{_n}.{attr}")
    sys.modules[name] = m


def _import_brain():
    sys.path.insert(0, str(REPO / "ml" / "src"))
    stubbed = []
    for _ in range(40):                       # stub each missing third-party module brain.planner pulls in
        try:
            from brain import planner as P
            from brain.catalog import Catalog
            from brain.decision import DecisionEngine
            return P, Catalog, DecisionEngine, stubbed
        except ModuleNotFoundError as e:
            if not e.name or e.name.startswith("brain"):
                raise
            for k in [k for k in sys.modules if k.startswith("brain")]:
                del sys.modules[k]
            _stub(e.name)
            stubbed.append(e.name)
    raise RuntimeError("too many missing modules")


P, Catalog, DecisionEngine, STUBBED = _import_brain()
CATALOG = Catalog.load(REPO / "skills" / "catalog.json")


def _sig(name: str) -> str:
    eng = DecisionEngine.__new__(DecisionEngine)
    eng.catalog = CATALOG
    return DecisionEngine.arg_signature(eng, name)


SYSTEM = P.planner_prompt(P.catalog_desc(CATALOG, _sig))


def login_page(state: dict) -> bool:
    window = re.match(r'^app: [^|]+ \| window: "((?:[^"\\]|\\.)*)"', state["observation"])
    return bool(LOGIN_RE.search(f"{window[1] if window else ''}\n{state['observation']}"))


def user_message(state: dict) -> str:
    return P.Planner.user_message(None, state["goal"], state["observation"], P.history(state.get("last_batch"), "dsl"),
                                  None, state.get("script_output"), login_page(state))


def messages(state: dict) -> list[dict]:
    return [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user_message(state)}]


if __name__ == "__main__":
    import json
    s = json.loads((REPO / "evals/planner_scenarios_v2.jsonl").read_text().splitlines()[0])
    print("stubbed:", STUBBED)
    for m in messages(s):
        print(f"--- {m['role']} ({len(m['content'])} chars)\n{m['content'][-700:] if m['role'] == 'system' else m['content']}")
