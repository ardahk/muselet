"""Option catalog (skills/catalog.json) as seen by the router."""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
CATALOG_PATH = REPO_ROOT / "skills" / "catalog.json"
SPECIAL = ("MULTI_STEP", "ASK", "REFUSE", "ANSWER")


@dataclass(frozen=True)
class Option:
    name: str
    description: str
    args: tuple[dict, ...] = ()
    examples: tuple[str, ...] = ()
    special: bool = False


@lru_cache(maxsize=1)
def load_catalog(path: Path = CATALOG_PATH) -> dict:
    return json.loads(Path(path).read_text())


def options(path: Path = CATALOG_PATH) -> list[Option]:
    """Catalog skills in file order, then the 4 special options in SPEC order."""
    cat = load_catalog(path)
    out = [
        Option(s["name"], s["description"], tuple(s.get("args", [])), tuple(s.get("examples", [])))
        for s in cat["skills"]
    ]
    special = {o["name"]: o["description"] for o in cat["special_options"]}
    out += [Option(n, special[n], special=True) for n in SPECIAL]
    return out


def skills(path: Path = CATALOG_PATH) -> list[Option]:
    return [o for o in options(path) if not o.special]


def option_names(path: Path = CATALOG_PATH) -> list[str]:
    return [o.name for o in options(path)]


def skill_by_name(name: str) -> Option:
    return {o.name: o for o in options()}[name]


def _arg_sig(a: dict) -> str:
    sig = f"{a['name']}:{a['type']}"
    if "min" in a or "max" in a:
        sig += f" {a.get('min', '')}-{a.get('max', '')}"
    if a.get("values"):
        sig += " " + "|".join(a["values"])
    return sig + (" required" if a.get("required") else " optional")


def arg_signature(opt: Option) -> str:
    """e.g. ``level:int 0-100 required, kind:enum any|pdf optional``."""
    return ", ".join(_arg_sig(a) for a in opt.args)
