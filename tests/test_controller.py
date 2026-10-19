import pytest

from echo6g.models import Scenario
from echo6g.policies import AdaptiveController, make_training_scenarios


def test_controller_requires_training():
    with pytest.raises(RuntimeError):
        AdaptiveController().choose(Scenario(30, 0.8, 30, 0.9))


def test_controller_returns_valid_action_after_training():
    controller = AdaptiveController().fit(make_training_scenarios(n=80))
    decision = controller.choose(Scenario(55, 0.8, 35, 0.93, "in_domain"))
    assert decision.resource_level in (1, 2, 3, 4)
    assert decision.explanation


def test_out_of_domain_triggers_fallback():
    controller = AdaptiveController().fit(make_training_scenarios(n=80))
    decision = controller.choose(Scenario(500, 0.8, 35, 0.93, "extreme"))
    assert decision.fallback_used is True
    assert decision.confidence < 0.5
