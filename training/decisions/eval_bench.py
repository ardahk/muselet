from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def wait_for_port(port: int, process: subprocess.Popen, timeout: float = 180) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"System One shim exited with code {process.returncode}")
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=1):
                return
        except OSError:
            time.sleep(1)
    raise TimeoutError(f"shim did not open port {port}")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Run full decision benchmarks against a Tinker sampler.")
    parser.add_argument("--sampler", required=True, help="tinker:// sampler path")
    parser.add_argument("--port", type=int, default=8794)
    parser.add_argument("--name", default="decision-sampler")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--calibration", type=Path)
    args = parser.parse_args(argv)
    if not args.sampler.startswith("tinker://"):
        parser.error("--sampler must be a tinker:// path")
    temperatures = {"temperature_probs": 1.0, "temperature_conf": 1.0}
    if args.calibration:
        temperatures.update(json.loads(args.calibration.read_text()))
    shim_command = [
        sys.executable, "-m", "bench.systemone.cli", "--backend", "tinker",
        "--model-path", args.sampler, "--port", str(args.port),
    ]
    if args.calibration:
        shim_command.extend(["--calibration", str(args.calibration)])
    shim = subprocess.Popen(shim_command, cwd=ROOT, env=os.environ.copy())
    try:
        wait_for_port(args.port, shim)
        url = f"http://127.0.0.1:{args.port}"
        runs = [
            ["bash", "bench/run_jevbench.sh", "--url", url, "--model", args.name],
            ["bash", "bench/run_typed_decisions.sh", "--url", url, "--model", args.name],
        ]
        results = []
        for command in runs:
            result = subprocess.run(command, cwd=ROOT, check=True, text=True, capture_output=True)
            results.append({"command": command, "stdout": result.stdout, "stderr": result.stderr})
        route_path = ROOT / "evals/route_v1.jsonl"
        route_note = (
            "Not scored: route_v1 rows are utterance/context/label/args records, not System One "
            "state/questions requests. Scoring requires cloud route rendering and label-space mapping; "
            "that renderer was not duplicated."
        ) if route_path.is_file() else "Not scored: evals/route_v1.jsonl is unavailable."
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps({
            "sampler": args.sampler,
            "calibration": temperatures,
            "confidence": (
                "Probabilities use T_p. Choice/score confidence is computed from a separate "
                "distribution using T_c; noul returns calibrated P(true) and has no confidence field."
            ),
            "benchmark_runs": results,
            "route_v1": route_note,
        }, indent=2) + "\n")
    finally:
        shim.terminate()
        try:
            shim.wait(timeout=10)
        except subprocess.TimeoutExpired:
            shim.kill()
            shim.wait()


if __name__ == "__main__":
    main()
