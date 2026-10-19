#include "engine.hpp"

#include <algorithm>
#include <array>
#include <cmath>
#include <fstream>
#include <iomanip>
#include <limits>
#include <numeric>
#include <sstream>
#include <stdexcept>
#include <tuple>

namespace echo6g {
namespace {

constexpr std::array<int, 4> kResourceLevels{1, 2, 3, 4};
constexpr std::array<const char*, 4> kPolicyNames{
    "energy_saver", "fixed_middle", "performance_first", "echo_adaptive"};
constexpr std::array<const char*, 4> kPolicyDescriptions{
    "Lowest provisioning baseline", "Fixed provisioning baseline",
    "Maximum provisioning baseline", "Context-aware adaptive policy"};
constexpr std::array<double, 4> kLatencyBudgets{18.0, 25.0, 35.0, 50.0};
constexpr std::array<double, 4> kTrainingReliability{0.90, 0.93, 0.95, 0.97};
constexpr std::array<double, 6> kTestLatencyBudgets{15.0, 18.0, 25.0, 35.0, 45.0, 55.0};
constexpr std::array<double, 5> kTestReliability{0.90, 0.93, 0.95, 0.97, 0.985};
constexpr std::size_t kFeatureCount = 5;

double rounded(double value, int decimals) {
    const double scale = std::pow(10.0, static_cast<double>(decimals));
    return std::round(value * scale) / scale;
}

std::string json_escape(const std::string& value) {
    std::ostringstream escaped;
    for (const unsigned char character : value) {
        switch (character) {
            case '"': escaped << "\\\""; break;
            case '\\': escaped << "\\\\"; break;
            case '\b': escaped << "\\b"; break;
            case '\f': escaped << "\\f"; break;
            case '\n': escaped << "\\n"; break;
            case '\r': escaped << "\\r"; break;
            case '\t': escaped << "\\t"; break;
            default:
                if (character < 0x20) {
                    escaped << "\\u" << std::hex << std::setw(4) << std::setfill('0')
                            << static_cast<int>(character) << std::dec;
                } else {
                    escaped << character;
                }
        }
    }
    return escaped.str();
}

std::string json_number(double value) {
    if (!std::isfinite(value)) {
        return "null";
    }
    std::ostringstream output;
    output << std::setprecision(15) << value;
    return output.str();
}

std::string csv_escape(const std::string& value) {
    std::string escaped{"\""};
    for (const char character : value) {
        if (character == '"') {
            escaped += "\"\"";
        } else {
            escaped += character;
        }
    }
    escaped += '"';
    return escaped;
}

class StableRandom {
public:
    explicit StableRandom(std::int64_t seed) : state_(static_cast<std::uint64_t>(seed)) {}

    std::uint64_t next() {
        state_ += 0x9E3779B97F4A7C15ULL;
        std::uint64_t value = state_;
        value = (value ^ (value >> 30U)) * 0xBF58476D1CE4E5B9ULL;
        value = (value ^ (value >> 27U)) * 0x94D049BB133111EBULL;
        return value ^ (value >> 31U);
    }

    double uniform(double low, double high) {
        constexpr double denominator = 9007199254740992.0;
        const double fraction = static_cast<double>(next() >> 11U) / denominator;
        return low + (high - low) * fraction;
    }

    std::size_t choose(std::size_t count) {
        return static_cast<std::size_t>(next() % count);
    }

private:
    std::uint64_t state_;
};

using Features = std::array<double, kFeatureCount>;
using Coefficients = std::array<double, kFeatureCount>;
using Matrix = std::array<std::array<double, kFeatureCount>, kFeatureCount>;

Features features(const Scenario& scenario) {
    return {1.0, scenario.traffic_mbps / 160.0, scenario.channel_quality,
            scenario.latency_budget_ms / 60.0, scenario.reliability_target};
}

double dot(const Features& left, const Coefficients& right) {
    double total = 0.0;
    for (std::size_t index = 0; index < kFeatureCount; ++index) {
        total += left[index] * right[index];
    }
    return total;
}

Coefficients solve(Matrix matrix, Coefficients vector) {
    for (std::size_t column = 0; column < kFeatureCount; ++column) {
        std::size_t pivot = column;
        for (std::size_t row = column + 1; row < kFeatureCount; ++row) {
            if (std::abs(matrix[row][column]) > std::abs(matrix[pivot][column])) {
                pivot = row;
            }
        }
        if (std::abs(matrix[pivot][column]) < 1e-12) {
            throw std::runtime_error("Could not train the adaptive strategy.");
        }
        std::swap(matrix[pivot], matrix[column]);
        std::swap(vector[pivot], vector[column]);
        const double divisor = matrix[column][column];
        for (std::size_t item = column; item < kFeatureCount; ++item) {
            matrix[column][item] /= divisor;
        }
        vector[column] /= divisor;
        for (std::size_t row = 0; row < kFeatureCount; ++row) {
            if (row == column) {
                continue;
            }
            const double factor = matrix[row][column];
            for (std::size_t item = column; item < kFeatureCount; ++item) {
                matrix[row][item] -= factor * matrix[column][item];
            }
            vector[row] -= factor * vector[column];
        }
    }
    return vector;
}

class AdaptiveController {
public:
    explicit AdaptiveController(const std::vector<Scenario>& scenarios) {
        fit(scenarios);
    }

    Decision choose(const Scenario& scenario) const {
        scenario.validate();
        if (outside_training_range(scenario)) {
            const int level = lowest_viable_level(scenario);
            return {"echo_adaptive", level,
                    "Out-of-range values detected; used a cautious target-aware fallback.",
                    0.25, true};
        }

        const Features values = features(scenario);
        struct Estimate {
            double reward{};
            double uncertainty{};
            int resource_level{};
        };
        std::array<Estimate, 4> estimates{};
        for (std::size_t index = 0; index < estimates.size(); ++index) {
            estimates[index] = {dot(values, coefficients_[index]), uncertainty_[index],
                                kResourceLevels[index]};
        }
        const auto best = std::max_element(estimates.begin(), estimates.end(),
            [](const Estimate& left, const Estimate& right) { return left.reward < right.reward; });
        const double confidence = std::clamp(std::exp(-best->uncertainty), 0.0, 1.0);
        if (best->uncertainty > uncertainty_threshold_) {
            return {"echo_adaptive", lowest_viable_level(scenario),
                    "The model is uncertain; used a cautious target-aware fallback.",
                    confidence, true};
        }
        std::ostringstream explanation;
        explanation << "Selected level " << best->resource_level
                    << " from model estimates; model uncertainty="
                    << std::fixed << std::setprecision(3) << best->uncertainty << '.';
        return {"echo_adaptive", best->resource_level, explanation.str(), confidence, false};
    }

private:
    std::array<Coefficients, 4> coefficients_{};
    std::array<double, 4> uncertainty_{};
    Features minimum_{};
    Features maximum_{};
    double uncertainty_threshold_{1.50};

    void fit(const std::vector<Scenario>& scenarios) {
        if (scenarios.size() < 12) {
            throw std::invalid_argument("Provide at least 12 training scenarios.");
        }
        minimum_.fill(std::numeric_limits<double>::infinity());
        maximum_.fill(-std::numeric_limits<double>::infinity());
        std::vector<Features> rows;
        rows.reserve(scenarios.size());
        for (const auto& scenario : scenarios) {
            scenario.validate();
            const Features row = features(scenario);
            rows.push_back(row);
            for (std::size_t feature = 1; feature < kFeatureCount; ++feature) {
                minimum_[feature] = std::min(minimum_[feature], row[feature]);
                maximum_[feature] = std::max(maximum_[feature], row[feature]);
            }
        }

        for (std::size_t action = 0; action < kResourceLevels.size(); ++action) {
            Matrix matrix{};
            Coefficients vector{};
            for (std::size_t feature = 1; feature < kFeatureCount; ++feature) {
                matrix[feature][feature] = 0.08;
            }
            std::vector<double> rewards;
            rewards.reserve(scenarios.size());
            for (const auto& scenario : scenarios) {
                rewards.push_back(evaluate(scenario,
                    {"training", kResourceLevels[action], "training sample"}).reward);
            }
            for (std::size_t sample = 0; sample < rows.size(); ++sample) {
                for (std::size_t left = 0; left < kFeatureCount; ++left) {
                    vector[left] += rows[sample][left] * rewards[sample];
                    for (std::size_t right = 0; right < kFeatureCount; ++right) {
                        matrix[left][right] += rows[sample][left] * rows[sample][right];
                    }
                }
            }
            coefficients_[action] = solve(matrix, vector);
            double squared_error = 0.0;
            for (std::size_t sample = 0; sample < rows.size(); ++sample) {
                const double residual = rewards[sample] - dot(rows[sample], coefficients_[action]);
                squared_error += residual * residual;
            }
            uncertainty_[action] = std::sqrt(squared_error / static_cast<double>(rows.size()));
        }
    }

    bool outside_training_range(const Scenario& scenario) const {
        const Features values = features(scenario);
        for (std::size_t feature = 1; feature < kFeatureCount; ++feature) {
            const double span = std::max(maximum_[feature] - minimum_[feature], 0.05);
            if (values[feature] < minimum_[feature] - 0.10 * span ||
                values[feature] > maximum_[feature] + 0.10 * span) {
                return true;
            }
        }
        return false;
    }

    static int lowest_viable_level(const Scenario& scenario) {
        for (const int level : kResourceLevels) {
            if (evaluate(scenario, {"fallback_check", level, ""}).sla_met) {
                return level;
            }
        }
        return kResourceLevels.back();
    }
};

std::vector<Outcome> evaluate_all(const Scenario& scenario, const AdaptiveController& adaptive) {
    const std::array<Decision, 3> baselines{
        Decision{"energy_saver", scenario.traffic_mbps < 25.0 ? 1 : 2,
                 "Energy-first baseline: selects a low resource level based on traffic only."},
        Decision{"fixed_middle", 2, "Fixed baseline: always selects resource level 2."},
        Decision{"performance_first", 4, "Performance-first baseline: selects the maximum resource level."},
    };
    std::vector<Outcome> outcomes;
    outcomes.reserve(4);
    for (const auto& baseline : baselines) {
        outcomes.push_back(evaluate(scenario, baseline));
    }
    outcomes.push_back(evaluate(scenario, adaptive.choose(scenario)));
    return outcomes;
}

std::string bool_text(bool value) {
    return value ? "true" : "false";
}

void write_benchmark_csv(const std::filesystem::path& path,
                         const std::vector<Outcome>& outcomes) {
    std::ofstream output(path, std::ios::binary);
    if (!output) {
        throw std::runtime_error("Could not create benchmark_results.csv.");
    }
    output << "scenario_name,policy_name,traffic_mbps,channel_quality,latency_budget_ms,"
              "reliability_target,resource_level,"
              "throughput_mbps,latency_ms,reliability,energy_units,sla_met,reward,"
              "explanation,confidence,fallback_used\r\n";
    for (const auto& row : outcomes) {
        output << csv_escape(row.scenario_name) << ',' << csv_escape(row.policy_name) << ','
               << json_number(row.traffic_mbps) << ',' << json_number(row.channel_quality) << ','
               << json_number(row.latency_budget_ms) << ',' << json_number(row.reliability_target) << ','
               << row.resource_level << ',' << json_number(row.throughput_mbps) << ','
               << json_number(row.latency_ms) << ',' << json_number(row.reliability) << ','
               << json_number(row.energy_units) << ',' << bool_text(row.sla_met) << ','
               << json_number(row.reward) << ',' << csv_escape(row.explanation) << ','
               << json_number(row.confidence) << ',' << bool_text(row.fallback_used) << "\r\n";
    }
}

void write_summary_csv(const std::filesystem::path& path,
                       const std::vector<BenchmarkSummary>& summaries) {
    std::ofstream output(path, std::ios::binary);
    if (!output) {
        throw std::runtime_error("Could not create benchmark_summary.csv.");
    }
    output << "policy,scenarios,sla_success_rate,mean_latency_ms,mean_energy_units,"
              "mean_reward,fallback_rate\r\n";
    for (const auto& row : summaries) {
        output << row.policy << ',' << row.scenarios << ','
               << json_number(row.sla_success_rate) << ',' << json_number(row.mean_latency_ms) << ','
               << json_number(row.mean_energy_units) << ',' << json_number(row.mean_reward) << ','
               << json_number(row.fallback_rate) << "\r\n";
    }
}

}  // namespace

void Scenario::validate() const {
    if (!std::isfinite(traffic_mbps) || !std::isfinite(channel_quality) ||
        !std::isfinite(latency_budget_ms) || !std::isfinite(reliability_target)) {
        throw std::invalid_argument("scenario values must be finite numbers");
    }
    if (traffic_mbps < 0.0 || traffic_mbps > 10'000.0) {
        throw std::invalid_argument("traffic_mbps must be between 0 and 10000 Mbps");
    }
    if (channel_quality < 0.25 || channel_quality > 1.0) {
        throw std::invalid_argument("channel_quality must be in [0.25, 1.0]");
    }
    if (latency_budget_ms <= 0.0 || latency_budget_ms > 10'000.0) {
        throw std::invalid_argument("latency_budget_ms must be greater than 0 and no more than 10000 ms");
    }
    if (reliability_target < 0.01 || reliability_target > 1.0) {
        throw std::invalid_argument("reliability_target must be between 0.01 and 1");
    }
}

Outcome evaluate(const Scenario& scenario, const Decision& decision) {
    scenario.validate();
    if (std::find(kResourceLevels.begin(), kResourceLevels.end(), decision.resource_level) ==
        kResourceLevels.end()) {
        throw std::invalid_argument("resource_level must be one of 1, 2, 3, 4");
    }

    const double capacity = static_cast<double>(decision.resource_level) * 38.0 * scenario.channel_quality;
    const double throughput = std::min(scenario.traffic_mbps, capacity);
    const double overload = std::max(0.0, scenario.traffic_mbps - capacity);
    const double latency = 8.0 + overload * 0.85 + (1.0 - scenario.channel_quality) * 18.0;
    const double overload_ratio = overload / std::max(scenario.traffic_mbps, 1.0);
    const double reliability = std::clamp(
        0.995 - 0.38 * overload_ratio - 0.16 * (1.0 - scenario.channel_quality), 0.50, 0.999);
    const double energy = std::pow(static_cast<double>(decision.resource_level), 1.45) *
                          (1.0 + 0.18 * (1.0 - scenario.channel_quality));
    const double reported_latency = rounded(latency, 3);
    const double reported_reliability = rounded(reliability, 5);
    const bool sla_met = reported_latency <= scenario.latency_budget_ms &&
                         reported_reliability >= scenario.reliability_target;
    const double throughput_fraction = throughput / std::max(scenario.traffic_mbps, 1.0);
    double reward = 0.0;
    if (sla_met) {
        reward = 0.72 * throughput_fraction + 0.28 / (1.0 + energy / 5.0);
    } else {
        const double latency_violation = std::max(0.0, latency - scenario.latency_budget_ms) /
                                         scenario.latency_budget_ms;
        const double reliability_violation = std::max(0.0, scenario.reliability_target - reliability);
        reward = -1.0 - 2.0 * latency_violation - 4.0 * reliability_violation +
                 0.05 * throughput_fraction;
    }

    return {scenario.name, decision.policy_name, rounded(scenario.traffic_mbps, 3),
            rounded(scenario.channel_quality, 3), rounded(scenario.latency_budget_ms, 3),
            rounded(scenario.reliability_target, 5), decision.resource_level,
            rounded(throughput, 3), reported_latency, reported_reliability,
            rounded(energy, 3), sla_met, rounded(reward, 5), decision.explanation,
            decision.confidence, decision.fallback_used};
}

std::vector<Scenario> make_training_scenarios(std::int64_t seed, std::size_t count) {
    if (count < 12) {
        throw std::invalid_argument("Provide at least 12 training scenarios.");
    }
    StableRandom random(seed);
    std::vector<Scenario> scenarios;
    scenarios.reserve(count);
    for (std::size_t index = 0; index < count; ++index) {
        scenarios.push_back({
            random.uniform(5.0, 150.0),
            random.uniform(0.35, 1.0),
            kLatencyBudgets[random.choose(kLatencyBudgets.size())],
            kTrainingReliability[random.choose(kTrainingReliability.size())],
            "train_" + std::to_string(index),
        });
    }
    return scenarios;
}

std::vector<Scenario> make_scenarios(std::int64_t seed, std::size_t count,
                                    const std::string& split) {
    StableRandom random(seed);
    std::vector<Scenario> scenarios;
    scenarios.reserve(count);
    for (std::size_t index = 0; index < count; ++index) {
        scenarios.push_back({
            random.uniform(8.0, 155.0),
            random.uniform(0.30, 1.0),
            kTestLatencyBudgets[random.choose(kTestLatencyBudgets.size())],
            kTestReliability[random.choose(kTestReliability.size())],
            split + "_" + std::to_string(index),
        });
    }
    return scenarios;
}

Evaluation evaluate_buyer(const Scenario& scenario) {
    scenario.validate();
    const auto training = make_training_scenarios(43, 240);
    const AdaptiveController adaptive(training);
    auto outcomes = evaluate_all(scenario, adaptive);
    std::vector<const Outcome*> viable;
    for (const auto& outcome : outcomes) {
        if (outcome.sla_met) {
            viable.push_back(&outcome);
        }
    }
    const Outcome* selected = nullptr;
    Recommendation recommendation;
    if (!viable.empty()) {
        selected = *std::min_element(viable.begin(), viable.end(),
            [](const Outcome* left, const Outcome* right) {
                return std::tie(left->energy_units, right->reward) <
                       std::tie(right->energy_units, left->reward);
            });
        recommendation = {"meets_sla", selected->policy_name, selected->resource_level,
            "Lowest modelled energy among options that meet both stated targets."};
    } else {
        selected = &*std::max_element(outcomes.begin(), outcomes.end(),
            [](const Outcome& left, const Outcome& right) { return left.reward < right.reward; });
        recommendation = {"no_fit", selected->policy_name, selected->resource_level,
            "No tested option meets both targets. This is the highest-scoring modelled option; review the gap before procurement."};
    }
    return {scenario, recommendation, std::move(outcomes)};
}

BenchmarkRun run_benchmark(const std::filesystem::path& output_dir, std::int64_t seed,
                           std::size_t count) {
    if (count < 1 || count > 10'000) {
        throw std::invalid_argument("n must be an integer between 1 and 10000");
    }
    const auto training = make_training_scenarios(seed + 1, 240);
    const AdaptiveController adaptive(training);
    const auto scenarios = make_scenarios(seed, count);
    BenchmarkRun result;
    result.outcomes.reserve(count * kResourceLevels.size());
    for (const auto& scenario : scenarios) {
        scenario.validate();
        auto outcomes = evaluate_all(scenario, adaptive);
        result.outcomes.insert(result.outcomes.end(), outcomes.begin(), outcomes.end());
    }

    result.summaries.reserve(kPolicyNames.size());
    for (std::size_t policy = 0; policy < kPolicyNames.size(); ++policy) {
        double sla_count = 0.0;
        double latency_total = 0.0;
        double energy_total = 0.0;
        double reward_total = 0.0;
        double fallback_count = 0.0;
        for (std::size_t index = policy; index < result.outcomes.size(); index += kPolicyNames.size()) {
            const auto& row = result.outcomes[index];
            sla_count += row.sla_met ? 1.0 : 0.0;
            latency_total += row.latency_ms;
            energy_total += row.energy_units;
            reward_total += row.reward;
            fallback_count += row.fallback_used ? 1.0 : 0.0;
        }
        const double denominator = static_cast<double>(count);
        result.summaries.push_back({kPolicyNames[policy], count,
            rounded(sla_count / denominator, 4), rounded(latency_total / denominator, 3),
            rounded(energy_total / denominator, 3), rounded(reward_total / denominator, 5),
            rounded(fallback_count / denominator, 4)});
    }

    std::filesystem::create_directories(output_dir);
    write_benchmark_csv(output_dir / "benchmark_results.csv", result.outcomes);
    write_summary_csv(output_dir / "benchmark_summary.csv", result.summaries);
    return result;
}

std::string to_json(const Evaluation& evaluation) {
    std::ostringstream json;
    json << "{\"scenario\":{\"traffic_mbps\":" << json_number(evaluation.scenario.traffic_mbps)
         << ",\"channel_quality\":" << json_number(evaluation.scenario.channel_quality)
         << ",\"latency_budget_ms\":" << json_number(evaluation.scenario.latency_budget_ms)
         << ",\"reliability_target\":" << json_number(evaluation.scenario.reliability_target)
         << "},\"recommendation\":{\"status\":\"" << json_escape(evaluation.recommendation.status)
         << "\",\"policy\":\"" << json_escape(evaluation.recommendation.policy)
         << "\",\"resource_level\":" << evaluation.recommendation.resource_level
         << ",\"reason\":\"" << json_escape(evaluation.recommendation.reason)
         << "\"},\"options\":[";
    for (std::size_t index = 0; index < evaluation.options.size(); ++index) {
        if (index > 0) {
            json << ',';
        }
        const auto& option = evaluation.options[index];
        const auto description = std::find(kPolicyNames.begin(), kPolicyNames.end(), option.policy_name);
        const std::size_t policy_index = static_cast<std::size_t>(description - kPolicyNames.begin());
        json << "{\"scenario_name\":\"" << json_escape(option.scenario_name)
             << "\",\"policy_name\":\"" << json_escape(option.policy_name)
             << "\",\"traffic_mbps\":" << json_number(option.traffic_mbps)
             << ",\"channel_quality\":" << json_number(option.channel_quality)
             << ",\"latency_budget_ms\":" << json_number(option.latency_budget_ms)
             << ",\"reliability_target\":" << json_number(option.reliability_target)
             << ",\"resource_level\":" << option.resource_level
             << ",\"throughput_mbps\":" << json_number(option.throughput_mbps)
             << ",\"latency_ms\":" << json_number(option.latency_ms)
             << ",\"reliability\":" << json_number(option.reliability)
             << ",\"energy_units\":" << json_number(option.energy_units)
             << ",\"sla_met\":" << bool_text(option.sla_met)
             << ",\"reward\":" << json_number(option.reward)
             << ",\"explanation\":\"" << json_escape(option.explanation)
             << "\",\"confidence\":" << json_number(option.confidence)
             << ",\"fallback_used\":" << bool_text(option.fallback_used)
             << ",\"description\":\"" << json_escape(kPolicyDescriptions[policy_index]) << "\"}";
    }
    json << "],\"model_notice\":\"Synthetic software model. No Ericsson catalogue, price, hardware measurement, or 3GPP-compliant simulation is used.\"}";
    return json.str();
}

std::string summaries_to_json(const std::vector<BenchmarkSummary>& summaries) {
    std::ostringstream json;
    json << '[';
    for (std::size_t index = 0; index < summaries.size(); ++index) {
        if (index > 0) {
            json << ',';
        }
        const auto& summary = summaries[index];
        json << "{\"policy\":\"" << json_escape(summary.policy)
             << "\",\"scenarios\":" << summary.scenarios
             << ",\"sla_success_rate\":" << json_number(summary.sla_success_rate)
             << ",\"mean_latency_ms\":" << json_number(summary.mean_latency_ms)
             << ",\"mean_energy_units\":" << json_number(summary.mean_energy_units)
             << ",\"mean_reward\":" << json_number(summary.mean_reward)
             << ",\"fallback_rate\":" << json_number(summary.fallback_rate) << '}';
    }
    json << ']';
    return json.str();
}

}  // namespace echo6g
