"""JSONL traces -> runs/traces/<date>.jsonl"""

import json
import time
from datetime import date, datetime
from pathlib import Path


class Tracer:
    def __init__(self, out_dir: str | Path = "runs/traces"):
        self.dir = Path(out_dir)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.current: dict | None = None

    def _file(self) -> Path:
        return self.dir / f"{date.today().isoformat()}.jsonl"

    def begin(self, utterance: str) -> dict:
        self.current = {
            "ts": datetime.now().isoformat(timespec="milliseconds"),
            "utterance": utterance,
            "rpc": [],
            "decisions": [],
            "stages": {},
            "outcome": None,
        }
        return self.current

    def rpc(self, method: str, params: dict, result, ms: float):
        if self.current is not None:
            self.current["rpc"].append({
                "method": method, "params": params, "result": result,
                "ms": round(ms, 2)})

    def decision(self, info: dict):
        if self.current is not None:
            self.current["decisions"].append(info)

    def stage(self, name: str, ms: float):
        if self.current is not None:
            self.current["stages"][name] = round(ms, 2)

    def event(self, kind: str, info: dict):
        row = {"ts": datetime.now().isoformat(timespec="milliseconds"),
               "event": kind, **info}
        with self._file().open("a") as f:
            f.write(json.dumps(row, default=str) + "\n")

    def finish(self, outcome: str):
        if self.current is None:
            return
        self.current["outcome"] = outcome
        self.current["total_ms"] = round(
            (time.time() - datetime.fromisoformat(
                self.current["ts"]).timestamp()) * 1000, 2)
        with self._file().open("a") as f:
            f.write(json.dumps(self.current, default=str) + "\n")
        self.current = None
