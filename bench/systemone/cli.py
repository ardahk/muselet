"""Start the local System One shim."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from .fake import FakeDecider
from .server import serve


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8793)
    parser.add_argument("--backend", choices=("fake", "mlx", "tinker"), default="fake")
    parser.add_argument("--model-path")
    parser.add_argument("--model-name", default="muselet")
    parser.add_argument("--temperature-probs", type=float, default=1.0)
    parser.add_argument("--temperature-conf", type=float, default=1.0)
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    if args.backend == "fake":
        decider = FakeDecider()
    else:
        if not args.model_path:
            parser.error(f"--model-path is required with --backend {args.backend}")
        repo = Path(__file__).resolve().parents[2]
        sys.path.insert(0, str(repo / "ml" / "src"))
        try:
            if args.backend == "mlx":
                from brain.generic_decide import GenericMLXDecider
                decider = GenericMLXDecider(args.model_path)
            else:
                from .tinker_backend import TinkerDecider
                decider = TinkerDecider(
                    args.model_path,
                    temperature_probs=args.temperature_probs,
                    temperature_conf=args.temperature_conf,
                )
        except Exception as exc:
            parser.error(f"could not initialize {args.backend} backend: {type(exc).__name__}: {exc}")

    try:
        serve(args.host, args.port, decider, args.model_name)
    except KeyboardInterrupt:
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
