#include "engine.hpp"

#include <cassert>
#include <cmath>
#include <stdexcept>

int main() {
    using namespace echo6g;

    const Scenario scenario{40.0, 0.9, 30.0, 0.90, "unit_test"};
    const Outcome outcome = evaluate(scenario, {"test", 2, "test explanation"});
    assert(outcome.throughput_mbps == 40.0);
    assert(outcome.latency_ms == 9.8);
    assert(outcome.reliability >= 0.0 && outcome.reliability <= 1.0);
    assert(outcome.energy_units > 0.0);
    assert(outcome.policy_name == "test");

    bool rejected = false;
    try {
        Scenario{40.0, 1.5, 30.0, 0.90}.validate();
    } catch (const std::invalid_argument&) {
        rejected = true;
    }
    assert(rejected);

    const Scenario invalid{40.0, 0.9, 30.0, 0.90};
    rejected = false;
    try {
        (void)evaluate(invalid, {"bad", 5, "bad"});
    } catch (const std::invalid_argument&) {
        rejected = true;
    }
    assert(rejected);

    const auto training_a = make_training_scenarios(43, 240);
    const auto training_b = make_training_scenarios(43, 240);
    assert(training_a.size() == 240);
    assert(training_a.front().traffic_mbps == training_b.front().traffic_mbps);
    const auto test_rows = make_scenarios(2026, 10'000);
    assert(test_rows.size() == 10'000);
    for (const auto& row : training_a) {
        row.validate();
    }
    for (const auto& row : test_rows) {
        row.validate();
    }

    const auto evaluated = evaluate_buyer({55.0, 0.9, 30.0, 0.93, "buyer_scenario"});
    assert(evaluated.options.size() == 4);
    assert(evaluated.recommendation.status == "meets_sla" ||
           evaluated.recommendation.status == "no_fit");
    for (const auto& option : evaluated.options) {
        assert(option.resource_level >= 1 && option.resource_level <= 4);
        assert(option.energy_units > 0.0);
        assert(std::isfinite(option.reward));
    }
    return 0;
}
