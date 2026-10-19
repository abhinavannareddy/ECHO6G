"""Shared data models for the ECHO-6G simulator."""
from __future__ import annotations

from dataclasses import dataclass, asdict
import math
from typing import Any


@dataclass(frozen=True)
class Scenario:
    """One simulated operating condition. Values are dimensionless/modelled."""
    traffic_mbps: float
    channel_quality: float  # 0.25 (poor) to 1.0 (excellent)
    latency_budget_ms: float
    reliability_target: float
    name: str = "custom"

    def validate(self) -> None:
        values = (self.traffic_mbps, self.channel_quality,
                  self.latency_budget_ms, self.reliability_target)
        if any(not math.isfinite(value) for value in values):
            raise ValueError("scenario values must be finite numbers")
        if self.traffic_mbps < 0:
            raise ValueError("traffic_mbps must be non-negative")
        if not 0.25 <= self.channel_quality <= 1.0:
            raise ValueError("channel_quality must be in [0.25, 1.0]")
        if self.latency_budget_ms <= 0:
            raise ValueError("latency_budget_ms must be positive")
        if not 0.0 < self.reliability_target <= 1.0:
            raise ValueError("reliability_target must be in (0, 1]")


@dataclass(frozen=True)
class Decision:
    policy_name: str
    resource_level: int
    explanation: str
    confidence: float = 1.0
    fallback_used: bool = False


@dataclass(frozen=True)
class Outcome:
    scenario_name: str
    policy_name: str
    traffic_mbps: float
    channel_quality: float
    resource_level: int
    throughput_mbps: float
    latency_ms: float
    reliability: float
    energy_units: float
    sla_met: bool
    reward: float
    explanation: str = ""
    confidence: float = 1.0
    fallback_used: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
