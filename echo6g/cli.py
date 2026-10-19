"""Command-line interface."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .benchmark import run_benchmark


def main() -> None:
    parser = argparse.ArgumentParser(description="Run ECHO-6G policy benchmark")
    parser.add_argument("--output", default="results", help="Directory for CSV outputs")
    parser.add_argument("--seed", type=int, default=2026, help="Deterministic benchmark seed")
    parser.add_argument("--scenarios", type=int, default=160, help="Number of held-out test scenarios")
    args = parser.parse_args()
    try:
        _, summary = run_benchmark(args.output, args.seed, args.scenarios)
    except ValueError as exc:
        parser.error(str(exc))
    print(json.dumps(summary, indent=2))
    print(f"\nWrote results to: {Path(args.output).resolve()}")


if __name__ == "__main__":
    main()
