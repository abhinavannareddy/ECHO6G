#include "engine.hpp"

#include <charconv>
#include <cmath>
#include <iostream>
#include <limits>
#include <stdexcept>
#include <string>

namespace {

double parse_number(const char* value, const char* field) {
    std::size_t used = 0;
    const std::string text(value);
    double number = 0.0;
    try {
        number = std::stod(text, &used);
    } catch (const std::exception&) {
        throw std::invalid_argument(std::string(field) + " must be a number.");
    }
    if (used != text.size() || !std::isfinite(number)) {
        throw std::invalid_argument(std::string(field) + " must be a finite number.");
    }
    return number;
}

std::int64_t parse_integer(const char* value, const char* field) {
    std::size_t used = 0;
    const std::string text(value);
    long long number = 0;
    try {
        number = std::stoll(text, &used);
    } catch (const std::exception&) {
        throw std::invalid_argument(std::string(field) + " must be an integer.");
    }
    if (used != text.size()) {
        throw std::invalid_argument(std::string(field) + " must be an integer.");
    }
    return static_cast<std::int64_t>(number);
}

std::size_t parse_count(const char* value) {
    const auto count = parse_integer(value, "n");
    if (count < 1 || count > 10'000) {
        throw std::invalid_argument("n must be an integer between 1 and 10000");
    }
    return static_cast<std::size_t>(count);
}

void print_help() {
    std::cout << "ECHO-6G native model engine\n"
              << "  echo6g-engine evaluate TRAFFIC CHANNEL LATENCY RELIABILITY\n"
              << "  echo6g-engine benchmark OUTPUT_DIR SEED SCENARIOS\n";
}

}  // namespace

int main(int argc, char** argv) {
    try {
        if (argc == 2 && std::string(argv[1]) == "--help") {
            print_help();
            return 0;
        }
        if (argc == 6 && std::string(argv[1]) == "evaluate") {
            const echo6g::Scenario scenario{
                parse_number(argv[2], "traffic_mbps"),
                parse_number(argv[3], "channel_quality"),
                parse_number(argv[4], "latency_budget_ms"),
                parse_number(argv[5], "reliability_target"),
                "buyer_scenario",
            };
            std::cout << echo6g::to_json(echo6g::evaluate_buyer(scenario)) << '\n';
            return 0;
        }
        if (argc == 5 && std::string(argv[1]) == "benchmark") {
            const auto seed = parse_integer(argv[3], "seed");
            const auto count = parse_count(argv[4]);
            const auto result = echo6g::run_benchmark(argv[2], seed, count);
            std::cout << echo6g::summaries_to_json(result.summaries) << '\n';
            return 0;
        }
        print_help();
        return 2;
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 2;
    }
}
