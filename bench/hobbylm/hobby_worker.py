"""Parent-clocked adapter around the pinned HobbyLM trial function."""

from __future__ import annotations

import argparse
import json
import re
import select
import sys
import time
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class SafetyBlocked(RuntimeError):
    pass


_BLOCKED_TOOL = re.compile(r"send|message|email|invite|attendee", re.IGNORECASE)
_CONFIRM_TOOL = re.compile(r"confirm", re.IGNORECASE)


def _emit(event: dict[str, Any]) -> None:
    print(json.dumps(event, ensure_ascii=False, default=str), flush=True)


def _wait_for_ack(timeout: float = 30) -> bool:
    ready, _, _ = select.select([sys.stdin], [], [], timeout)
    if not ready:
        return False
    try:
        return json.loads(sys.stdin.readline()).get("ack") is True
    except (json.JSONDecodeError, AttributeError):
        return False


def _guard_native_helpers(helper, mcp, emit: Callable[[dict[str, Any]], None]) -> None:
    if getattr(mcp, "_bench_guard_installed", False):
        return
    original_create = helper.CAL.create_event

    def safe_create_event(*args, **kwargs):
        plan = args[0] if args else None
        has_email = bool(getattr(plan, "email", None)) or any(
            isinstance(value, str) and "@" in value for value in args
        )
        if kwargs.get("with_invite") is True or has_email:
            emit({"ev": "safety_blocked", "helper": "create_event"})
            raise SafetyBlocked("blocked by bench safety guard")
        return original_create(*args, **kwargs)

    helper.CAL.create_event = safe_create_event
    original_call = mcp.call

    def safe_call(tool: str, arguments: dict):
        if _CONFIRM_TOOL.search(tool):
            emit({"ev": "confirm_asked", "helper": tool})
            return {"ok": False, "confirmed": False, "yes": False}
        if _BLOCKED_TOOL.search(tool):
            emit({"ev": "safety_blocked", "helper": tool})
            raise SafetyBlocked("blocked by bench safety guard")
        return original_call(tool, arguments)

    mcp.call = safe_call
    mcp._bench_guard_installed = True


def run_task(
    helper,
    model,
    mcp,
    item: tuple[str, str, str, str],
    emit: Callable[[dict[str, Any]], None] = _emit,
    wait_for_ack: Callable[[float], bool] = _wait_for_ack,
) -> dict[str, Any]:
    task_id, *_ = item
    _guard_native_helpers(helper, mcp, emit)
    original_complete = model.complete
    original_validate = helper.validate
    original_sh = helper.sh
    original_snapshot = helper.snapshot
    sent = set()

    def complete(*args, **kwargs):
        if "t0" not in sent:
            sent.add("t0")
            emit({"ev": "t0", "task_id": task_id})
        return original_complete(*args, **kwargs)

    def validate(proposal, *args, **kwargs):
        result = original_validate(proposal, *args, **kwargs)
        kind = str(proposal.get("kind", "")).upper()
        if (
            result == "valid" and proposal.get("format_ok", True)
            and kind not in {"", "DONE", "UNKNOWN", "NONE"}
            and "first_action" not in sent
        ):
            sent.add("first_action")
            emit({"ev": "first_action", "task_id": task_id})
        return result

    def sh(*args, **kwargs):
        if (
            "pre_teardown" not in sent
            and len(args) >= 2
            and str(args[0]) == str(helper.WORK / "brightness")
            and args[1] == "set"
        ):
            sent.add("pre_teardown")
            emit({"ev": "pre_teardown", "task_id": task_id})
            if not wait_for_ack(30):
                raise TimeoutError("parent did not acknowledge pre-teardown snapshot")
        return original_sh(*args, **kwargs)

    def snapshot(*args, **kwargs):
        result = original_snapshot(*args, **kwargs)
        if "setup_done" not in sent:
            sent.add("setup_done")
            emit({"ev": "setup_done", "task_id": task_id})
            if not wait_for_ack(30):
                raise TimeoutError("parent did not acknowledge setup snapshot")
        return result

    model.complete = complete
    helper.validate = validate
    helper.sh = sh
    helper.snapshot = snapshot
    try:
        try:
            row = helper.trial(model, mcp, item)
        except SafetyBlocked as exc:
            row = {
                "id": task_id,
                "safety_blocked": True,
                "safety_error": str(exc),
            }
        emit({"ev": "done", "task_id": task_id, "row": row})
        return row
    finally:
        model.complete = original_complete
        helper.validate = original_validate
        helper.sh = original_sh
        helper.snapshot = original_snapshot


def _load_upstream(home: Path, model_name: str, round_name: str, runtime: str):
    import os

    os.environ["HOBBY_HOME"] = str(home)
    sys.path.insert(0, str(home / "hobby"))
    sys.path.insert(0, str(ROOT / "bench/hobbylm/upstream/hobby"))
    import hobbymac_run as helper
    helper.ROOT = home
    helper.WORK = home / "data"
    helper.SYSTEM_IN_USE = helper.SYSTEM_V2 if round_name in ("r3", "r4") else helper.SYSTEM
    helper.TEST_CAL = "Muselet Bench"
    adapter = round_name
    if runtime == "mlx":
        from mlx_runtime import MlxHobby
        model = MlxHobby(home / f"hobbymac-lora-{adapter}-ab.npz") if model_name == "trained" else MlxHobby()
    elif model_name == "trained":
        from torch_runtime import TorchHobby
        result_name = "hobbymac-train-results.json" if adapter == "r1" else f"hobbymac-train-results-{adapter}.json"
        model_path = home / ("hobbymac-lora.pt" if adapter == "r1" else f"hobbymac-lora-{adapter}.pt")
        metadata = json.loads((home / result_name).read_text(encoding="utf-8"))
        model = TorchHobby(model_path, metadata["adapter_sha256"])
    else:
        from torch_runtime import TorchHobby
        model = TorchHobby()
    return helper, model, helper.MCP()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hobby-home", type=Path, required=True)
    parser.add_argument("--model", choices=("trained", "untrained"), default="trained")
    parser.add_argument("--round", choices=("r1", "r2", "r3", "r4"), default="r4")
    parser.add_argument("--runtime", choices=("mlx", "torch"), default="mlx")
    args = parser.parse_args(argv)
    helper, model, mcp = _load_upstream(args.hobby_home, args.model, args.round, args.runtime)
    try:
        for line in sys.stdin:
            if not line.strip():
                continue
            task = json.loads(line)
            item = (task["id"], task["kind"], task["text"], task["expected"])
            run_task(helper, model, mcp, item)
    finally:
        mcp.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
