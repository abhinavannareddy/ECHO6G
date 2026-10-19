#pragma once

#include <cstdint>
#include <filesystem>
#include <string>
#include <vector>

namespace echo6g {

struct Scenario {
    double traffic_mbps{};
    double channel_quality{};
    double latency_budget_ms{};
    double reliability_target{};
    std::string name{"custom"};

    void validate() const;
};

struct Decision {
    std::string policy_name;
    int resource_level{};
    std::string explanation;
    double confidence{1.0};
    bool fallback_used{false};
};

struct Outcome {
    std::string scenario_name;
    std::string policy_name;
    double traffic_mbps{};
    double channel_quality{};
    double latency_budget_ms{};
    double reliability_target{};
    int resource_level{};
    double throughput_mbps{};
    double latency_ms{};
    double reliability{};
    double energy_units{};
    bool sla_met{false};
    double reward{};
    std::string explanation;
    double confidence{1.0};
    bool fallback_used{false};
};

struct Recommendation {
    std::string status;
    std::string policy;
    int resource_level{};
    std::string reason;
};

struct Evaluation {
    Scenario scenario;
    Recommendation recommendation;
    std::vector<Outcome> options;
};

struct BenchmarkSummary {
    std::string policy;
    std::size_t scenarios{};
    double sla_success_rate{};
    double mean_latency_ms{};
    double mean_energy_units{};
    double mean_reward{};
    double fallback_rate{};
};

struct BenchmarkRun {
    std::vector<Outcome> outcomes;
    std::vector<BenchmarkSummary> summaries;
};

Outcome evaluate(const Scenario& scenario, const Decision& decision);
Evaluation evaluate_buyer(const Scenario& scenario);
std::vector<Scenario> make_training_scenarios(std::int64_t seed, std::size_t count);
std::vector<Scenario> make_scenarios(std::int64_t seed, std::size_t count, const std::string& split = "test");
BenchmarkRun run_benchmark(const std::filesystem::path& output_dir, std::int64_t seed, std::size_t count);
std::string to_json(const Evaluation& evaluation);
std::string summaries_to_json(const std::vector<BenchmarkSummary>& summaries);

}  // namespace echo6g
