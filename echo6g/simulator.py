"""A deliberately simplified, transparent radio-resource simulator.

This is an educational model, not a 3GPP-compliant simulator or a physical
radio energy model. All energy values are relative model units.
"""
from __future__ import annotations

from .models import Scenario, Decision, Outcome


RESOURCE_LEVELS = (1, 2, 3, 4)


def evaluate(scenario: Scenario, decision: Decision) -> Outcome:
    scenario.validate()
    if decision.resource_level not in RESOURCE_LEVELS:
        raise ValueError(f"resource_level must be one of {RESOURCE_LEVELS}")

    # Capacity is affected by provisioned resources and channel quality.
    # The constants are illustrative and are documented in docs/MODEL.md.
    capacity = decision.resource_level * 38.0 * scenario.channel_quality
    throughput = min(scenario.traffic_mbps, capacity)
    overload = max(0.0, scenario.traffic_mbps - capacity)

    # Congestion and poor channel quality increase delay.
    latency = 8.0 + (overload * 0.85) + (1.0 - scenario.channel_quality) * 18.0

    # A transparent synthetic reliability estimate: overload and poor channel
    # quality lower the probability of successful service.
    overload_ratio = overload / max(scenario.traffic_mbps, 1.0)
    reliability = max(0.50, min(0.999, 0.995 - 0.38 * overload_ratio - 0.16 * (1.0 - scenario.channel_quality)))

    # Relative energy units. This is a model proxy, not measured Joules.
    energy = (decision.resource_level ** 1.45) * (1.0 + 0.18 * (1.0 - scenario.channel_quality))

    sla_met = latency <= scenario.latency_budget_ms and reliability >= scenario.reliability_target

    # Reward strongly penalizes SLA violations. Among SLA-compliant choices,
    # it favors useful throughput and lower energy.
    throughput_fraction = throughput / max(scenario.traffic_mbps, 1.0)
    if sla_met:
        reward = 0.72 * throughput_fraction + 0.28 / (1.0 + energy / 5.0)
    else:
        latency_violation = max(0.0, latency - scenario.latency_budget_ms) / scenario.latency_budget_ms
        reliability_violation = max(0.0, scenario.reliability_target - reliability)
        reward = -1.0 - 2.0 * latency_violation - 4.0 * reliability_violation + 0.05 * throughput_fraction

    return Outcome(
        scenario_name=scenario.name,
        policy_name=decision.policy_name,
        traffic_mbps=round(scenario.traffic_mbps, 3),
        channel_quality=round(scenario.channel_quality, 3),
        resource_level=decision.resource_level,
        throughput_mbps=round(throughput, 3),
        latency_ms=round(latency, 3),
        reliability=round(reliability, 5),
        energy_units=round(energy, 3),
        sla_met=sla_met,
        reward=round(reward, 5),
        explanation=decision.explanation,
        confidence=decision.confidence,
        fallback_used=decision.fallback_used,
    )
