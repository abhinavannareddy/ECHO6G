"""Baseline and adaptive resource-allocation policies."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
import math

import numpy as np

from .models import Scenario, Decision
from .simulator import RESOURCE_LEVELS, evaluate


class Policy(Protocol):
    name: str
    def choose(self, scenario: Scenario) -> Decision: ...


@dataclass
class EnergySaver:
    name: str = "energy_saver"
    def choose(self, scenario: Scenario) -> Decision:
        # Aggressively selects low resources; useful as a deliberately simple baseline.
        level = 1 if scenario.traffic_mbps < 25 else 2
        return Decision(self.name, level, "Energy-first baseline: selects a low resource level based on traffic only.")


@dataclass
class PerformanceFirst:
    name: str = "performance_first"
    def choose(self, scenario: Scenario) -> Decision:
        return Decision(self.name, 4, "Performance-first baseline: provisions the maximum resource level.")


@dataclass
class FixedMiddle:
    name: str = "fixed_middle"
    def choose(self, scenario: Scenario) -> Decision:
        return Decision(self.name, 2, "Fixed baseline: always provisions resource level 2.")


class AdaptiveController:
    """Contextual policy chooser with uncertainty and out-of-domain fallback.

    The model is intentionally transparent: it learns a linear reward model for
    each action from simulated training examples. At inference it estimates each
    action's reward and uncertainty. If context is outside the validated range,
    or uncertainty is too high, it falls back to a conservative rule.
    """
    name = "echo_adaptive"

    def __init__(self, uncertainty_threshold: float = 1.50) -> None:
        self.uncertainty_threshold = uncertainty_threshold
        self.models: dict[int, tuple[np.ndarray, np.ndarray]] = {}
        self.feature_min: np.ndarray | None = None
        self.feature_max: np.ndarray | None = None
        self.trained = False

    @staticmethod
    def features(s: Scenario) -> np.ndarray:
        # Normalized context plus an intercept.
        return np.array([1.0, s.traffic_mbps / 160.0, s.channel_quality,
                         s.latency_budget_ms / 60.0, s.reliability_target], dtype=float)

    def fit(self, scenarios: list[Scenario]) -> "AdaptiveController":
        if len(scenarios) < 12:
            raise ValueError("Provide at least 12 training scenarios")
        x_all = np.vstack([self.features(s) for s in scenarios])
        self.feature_min = x_all[:, 1:].min(axis=0)
        self.feature_max = x_all[:, 1:].max(axis=0)
        ridge = np.eye(x_all.shape[1]) * 0.08
        ridge[0, 0] = 0.0
        for action in RESOURCE_LEVELS:
            rewards = []
            for s in scenarios:
                outcome = evaluate(s, Decision("training", action, "training sample"))
                rewards.append(outcome.reward)
            y = np.asarray(rewards, dtype=float)
            beta = np.linalg.solve(x_all.T @ x_all + ridge, x_all.T @ y)
            residuals = y - x_all @ beta
            sigma = float(np.sqrt(np.mean(residuals ** 2)))
            self.models[action] = (beta, np.array([sigma]))
        self.trained = True
        return self

    def _is_out_of_domain(self, s: Scenario) -> bool:
        if self.feature_min is None or self.feature_max is None:
            return True
        values = self.features(s)[1:]
        # Allow a modest 10% margin around training range.
        span = np.maximum(self.feature_max - self.feature_min, 0.05)
        return bool(np.any(values < self.feature_min - 0.10 * span) or
                    np.any(values > self.feature_max + 0.10 * span))

    def choose(self, scenario: Scenario) -> Decision:
        if not self.trained:
            raise RuntimeError("Controller must be fit before use")
        scenario.validate()
        if self._is_out_of_domain(scenario):
            # Safe fallback: pick the smallest action predicted to satisfy the SLA;
            # if none does, choose max resources and expose the fallback explicitly.
            viable = []
            for action in RESOURCE_LEVELS:
                outcome = evaluate(scenario, Decision("fallback_check", action, ""))
                if outcome.sla_met:
                    viable.append((action, outcome.energy_units))
            level = min(viable, key=lambda item: item[1])[0] if viable else max(RESOURCE_LEVELS)
            return Decision(self.name, level,
                            "Out-of-domain context detected; used conservative SLA-aware fallback.",
                            confidence=0.25, fallback_used=True)

        x = self.features(scenario)
        estimates: list[tuple[float, float, int]] = []
        for action, (beta, sigma_arr) in self.models.items():
            estimate = float(x @ beta)
            sigma = float(sigma_arr[0])
            estimates.append((estimate, sigma, action))
        best = max(estimates, key=lambda item: item[0])
        confidence = max(0.0, min(1.0, math.exp(-best[1])))
        if best[1] > self.uncertainty_threshold:
            # Conservative fallback inside domain if model residual uncertainty is high.
            viable = [a for _, _, a in estimates if evaluate(scenario, Decision("check", a, "")).sla_met]
            level = min(viable) if viable else max(RESOURCE_LEVELS)
            return Decision(self.name, level,
                            f"Model uncertainty {best[1]:.3f} exceeded threshold; used SLA-aware fallback.",
                            confidence=confidence, fallback_used=True)
        return Decision(self.name, best[2],
                        f"Selected resource level {best[2]} from contextual reward estimates; residual uncertainty={best[1]:.3f}.",
                        confidence=confidence, fallback_used=False)


def make_training_scenarios(seed: int = 42, n: int = 240) -> list[Scenario]:
    rng = np.random.default_rng(seed)
    scenarios: list[Scenario] = []
    for i in range(n):
        traffic = float(rng.uniform(5, 150))
        channel = float(rng.uniform(0.35, 1.0))
        latency_budget = float(rng.choice([18, 25, 35, 50]))
        reliability_target = float(rng.choice([0.90, 0.93, 0.95, 0.97]))
        scenarios.append(Scenario(traffic, channel, latency_budget, reliability_target, f"train_{i:04d}"))
    return scenarios
