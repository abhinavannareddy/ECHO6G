"""Python entry point for benchmark runs in the native C++ engine."""
from __future__ import annotations

import csv
from pathlib import Path
import json

from .native import run_engine


def run_benchmark(output_dir: str | Path, seed: int = 2026, n: int = 160) -> tuple[list[dict[str, str]], list[dict[str, float | int | str]]]:
    if isinstance(n, bool) or not isinstance(n, int) or not 1 <= n <= 10_000:
        raise ValueError("n must be an integer between 1 and 10000")
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise ValueError("seed must be an integer")
    outdir = Path(output_dir)
    outdir.mkdir(parents=True, exist_ok=True)
    try:
        output = run_engine("benchmark", str(outdir.resolve()), str(seed), str(n), timeout=300.0)
    except ValueError:
        raise
    summaries = json.loads(output)
    csv_path = outdir / "benchmark_results.csv"
    with csv_path.open(newline="", encoding="utf-8") as source:
        outcomes = list(csv.DictReader(source))
    return outcomes, summaries
