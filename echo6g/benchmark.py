"""Repeatable policy evaluation and CSV reporting."""
from __future__ import annotations

import csv
from pathlib import Path
from statistics import mean

import numpy as np

from .models import Scenario, Decision, Outcome
from .policies import EnergySaver, PerformanceFirst, FixedMiddle, AdaptiveController, make_training_scenarios
from .simulator import evaluate, RESOURCE_LEVELS


def make_scenarios(seed: int = 2026, n: int = 160, split: str = "test") -> list[Scenario]:
    rng = np.random.default_rng(seed)
    items = []
    for i in range(n):
        # Test ranges overlap with training but include more difficult combinations.
        traffic = float(rng.uniform(8, 155))
        channel = float(rng.uniform(0.30, 1.0))
        latency_budget = float(rng.choice([15, 18, 25, 35, 45, 55]))
        reliability_target = float(rng.choice([0.90, 0.93, 0.95, 0.97, 0.985]))
        items.append(Scenario(traffic, channel, latency_budget, reliability_target, f"{split}_{i:04d}"))
    return items


def run_benchmark(output_dir: str | Path, seed: int = 2026, n: int = 160) -> tuple[list[Outcome], list[dict[str, float | str]]]:
    if isinstance(n, bool) or not isinstance(n, int) or not 1 <= n <= 10_000:
        raise ValueError("n must be an integer between 1 and 10000")
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise ValueError("seed must be an integer")
    outdir = Path(output_dir)
    outdir.mkdir(parents=True, exist_ok=True)
    training = make_training_scenarios(seed=seed + 1, n=240)
    adaptive = AdaptiveController().fit(training)
    policies = [EnergySaver(), FixedMiddle(), PerformanceFirst(), adaptive]
    scenarios = make_scenarios(seed=seed, n=n)
    outcomes: list[Outcome] = []
    for scenario in scenarios:
        for policy in policies:
            decision = policy.choose(scenario)
            outcomes.append(evaluate(scenario, decision))

    csv_path = outdir / "benchmark_results.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(outcomes[0].to_dict().keys()))
        writer.writeheader()
        writer.writerows([o.to_dict() for o in outcomes])

    summaries: list[dict[str, float | str]] = []
    for policy in policies:
        rows = [o for o in outcomes if o.policy_name == policy.name]
        summaries.append({
            "policy": policy.name,
            "scenarios": len(rows),
            "sla_success_rate": round(mean(float(o.sla_met) for o in rows), 4),
            "mean_latency_ms": round(mean(o.latency_ms for o in rows), 3),
            "mean_energy_units": round(mean(o.energy_units for o in rows), 3),
            "mean_reward": round(mean(o.reward for o in rows), 5),
            "fallback_rate": round(mean(float(o.fallback_used) for o in rows), 4),
        })
    summary_path = outdir / "benchmark_summary.csv"
    with summary_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(summaries[0].keys()))
        writer.writeheader()
        writer.writerows(summaries)
    return outcomes, summaries
