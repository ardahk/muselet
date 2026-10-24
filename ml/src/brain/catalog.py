"""Load and validate skills/catalog.json — the single source of truth."""

import os
from datetime import datetime
from pathlib import Path


class CatalogError(ValueError):
    pass


def default_path() -> Path:
    env = os.environ.get("MUSELET_SKILLS")
    if env:
        return Path(env)
    here = Path(__file__).resolve()
    for d in [Path.cwd(), *Path.cwd().parents, *here.parents]:
        p = d / "skills" / "catalog.json"
        if p.exists():
            return p
    raise FileNotFoundError("skills/catalog.json not found")


_TYPES = {"int", "float", "bool", "string", "enum", "datetime",
          "duration", "path", "app", "url", "contact"}


class Catalog:
    def __init__(self, data: dict):
        self.version = data.get("version", 0)
        self.skills = {s["name"]: s for s in data.get("skills", [])}
        self.special_options = data.get("special_options", [])

    @classmethod
    def load(cls, path: str | Path | None = None) -> "Catalog":
        import json
        p = Path(path) if path else default_path()
        return cls(json.loads(p.read_text()))

    def get(self, name: str) -> dict | None:
        return self.skills.get(name)

    def risk(self, name: str) -> str:
        s = self.skills.get(name)
        return s["risk"] if s else "safe"

    def validate_args(self, name: str, args: dict) -> dict:
        """Check required args and coerce types. Returns cleaned args."""
        spec = self.skills.get(name)
        if spec is None:
            raise CatalogError(f"unknown skill {name!r}")
        spec_args = {a["name"]: a for a in spec.get("args", [])}
        out = {}
        for key, val in args.items():
            if key == "confirmed":        # confirm-gate flag, not a spec arg
                out[key] = bool(val)
                continue
            if key not in spec_args:
                raise CatalogError(f"{name}: unknown arg {key!r}")
            out[key] = self._coerce(spec_args[key], val)
        for a in spec.get("args", []):
            if a.get("required") and a["name"] not in out:
                raise CatalogError(f"{name}: missing required arg {a['name']!r}")
        one_of = spec.get("require_one_of", [])
        if one_of and not any(key in out and out[key] not in (None, "")
                              for key in one_of):
            raise CatalogError(
                f"{name}: requires one of {', '.join(one_of)}")
        return out

    @staticmethod
    def _coerce(spec: dict, val):
        t = spec.get("type", "string")
        name = spec["name"]
        try:
            if t == "int":
                v = int(val)
                if "min" in spec and v < spec["min"]:
                    raise CatalogError(f"{name}: {v} < min {spec['min']}")
                if "max" in spec and v > spec["max"]:
                    raise CatalogError(f"{name}: {v} > max {spec['max']}")
                return v
            if t == "float":
                return float(val)
            if t == "bool":
                if isinstance(val, bool):
                    return val
                if isinstance(val, str):
                    if val.lower() in ("true", "1", "yes", "on"):
                        return True
                    if val.lower() in ("false", "0", "no", "off"):
                        return False
                if isinstance(val, (int, float)):
                    return bool(val)
                raise ValueError(val)
            if t == "enum":
                if val not in spec.get("values", []):
                    raise CatalogError(
                        f"{name}: {val!r} not in {spec.get('values')}")
                return val
            if t == "datetime":
                if isinstance(val, datetime):
                    return val.isoformat()
                s = str(val)
                datetime.fromisoformat(s)  # raises on bad input
                return s
            return str(val)
        except CatalogError:
            raise
        except Exception as e:
            raise CatalogError(f"{name}: cannot coerce {val!r} to {t}") from e
