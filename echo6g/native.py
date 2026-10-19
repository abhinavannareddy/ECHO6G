"""Python bridge to the C++ model engine."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
from typing import Any


def engine_path() -> Path:
    """Find the compiled C++ engine or explain how to build it."""
    configured = os.environ.get("ECHO6G_ENGINE")
    candidates = [Path(configured)] if configured else []
    package = Path(__file__).resolve().parent
    root = package.parent
    candidates.extend([
        Path("/usr/local/bin/echo6g-engine"),
        package / "native" / "build" / "echo6g-engine",
        package / "native" / "build" / "echo6g-engine.exe",
        root / "build" / "native" / "echo6g-engine",
        root / "build" / "native" / "echo6g-engine.exe",
        root / "build" / "native" / "Release" / "echo6g-engine.exe",
    ])
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise RuntimeError(
        "The C++ model engine is not built. Follow the build steps in README.md, "
        "or run the app with Docker."
    )


def run_engine(*arguments: str, timeout: float = 120.0) -> str:
    """Run the native model and return standard output."""
    try:
        result = subprocess.run(
            [str(engine_path()), *arguments],
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("The C++ model engine took too long to respond.") from exc
    if result.returncode != 0:
        message = result.stderr.strip() or "The C++ model engine could not complete the request."
        if result.returncode == 2:
            raise ValueError(message)
        raise RuntimeError(message)
    return result.stdout


def evaluate_native(values: dict[str, float]) -> dict[str, Any]:
    """Evaluate one buyer scenario in the C++ engine."""
    output = run_engine(
        "evaluate",
        format(values["traffic_mbps"], ".17g"),
        format(values["channel_quality"], ".17g"),
        format(values["latency_budget_ms"], ".17g"),
        format(values["reliability_target"], ".17g"),
    )
    try:
        return json.loads(output)
    except json.JSONDecodeError as exc:
        raise RuntimeError("The C++ model engine returned an unreadable result.") from exc
