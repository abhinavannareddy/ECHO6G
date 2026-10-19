import pytest

from echo6g.models import Scenario, Decision
from echo6g.simulator import evaluate


def test_evaluate_returns_valid_metrics():
    scenario = Scenario(40, 0.9, 30, 0.90, "test")
    outcome = evaluate(scenario, Decision("test", 2, "test explanation"))
    assert outcome.throughput_mbps >= 0
    assert 0.0 <= outcome.reliability <= 1.0
    assert outcome.energy_units > 0
    assert outcome.policy_name == "test"


def test_invalid_channel_quality_rejected():
    with pytest.raises(ValueError):
        Scenario(40, 1.5, 30, 0.90).validate()


@pytest.mark.parametrize("scenario", [
    Scenario(float("nan"), 0.9, 30, 0.9),
    Scenario(40, 0.9, float("inf"), 0.9),
    Scenario(40, 0.9, 30, float("nan")),
])
def test_non_finite_scenario_inputs_rejected(scenario):
    with pytest.raises(ValueError, match="finite"):
        scenario.validate()


def test_invalid_resource_level_rejected():
    with pytest.raises(ValueError):
        evaluate(Scenario(40, 0.9, 30, 0.90), Decision("bad", 5, "bad"))
