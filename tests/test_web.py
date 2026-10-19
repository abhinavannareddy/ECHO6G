import math

import pytest

from echo6g.web import evaluate_scenario
from echo6g.benchmark import run_benchmark


def test_buyer_evaluation_returns_four_comparable_options():
    result = evaluate_scenario({
        "traffic_mbps": 85,
        "channel_quality": 0.82,
        "latency_budget_ms": 35,
        "reliability_target": 0.93,
    })

    assert len(result["options"]) == 4
    assert {option["policy_name"] for option in result["options"]} == {
        "energy_saver", "fixed_middle", "performance_first", "echo_adaptive"
    }
    assert result["recommendation"]["status"] in {"meets_sla", "no_fit"}
    if result["recommendation"]["status"] == "meets_sla":
        selected = next(option for option in result["options"]
                        if option["policy_name"] == result["recommendation"]["policy"])
        assert selected["sla_met"] is True


@pytest.mark.parametrize("field,value", [
    ("traffic_mbps", -1),
    ("channel_quality", 1.01),
    ("latency_budget_ms", 0),
    ("reliability_target", 1.1),
    ("traffic_mbps", math.inf),
    ("traffic_mbps", math.nan),
])
def test_buyer_evaluation_rejects_invalid_inputs(field, value):
    scenario = {
        "traffic_mbps": 85,
        "channel_quality": 0.82,
        "latency_budget_ms": 35,
        "reliability_target": 0.93,
    }
    scenario[field] = value
    with pytest.raises(ValueError):
        evaluate_scenario(scenario)


def test_buyer_evaluation_rejects_missing_inputs():
    with pytest.raises(ValueError, match="Missing required fields"):
        evaluate_scenario({"traffic_mbps": 85})


def test_benchmark_rejects_empty_or_oversized_runs():
    with pytest.raises(ValueError, match="between 1 and 10000"):
        run_benchmark("unused-output", n=0)
    with pytest.raises(ValueError, match="between 1 and 10000"):
        run_benchmark("unused-output", n=10_001)
