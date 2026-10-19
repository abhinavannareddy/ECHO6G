import unittest

from echo6g.web import evaluate_scenario


class AdaptivePolicyTests(unittest.TestCase):
    def test_out_of_range_scenario_marks_adaptive_fallback(self):
        result = evaluate_scenario({
            "traffic_mbps": 500,
            "channel_quality": 0.8,
            "latency_budget_ms": 35,
            "reliability_target": 0.93,
        })
        adaptive = next(option for option in result["options"]
                        if option["policy_name"] == "echo_adaptive")
        self.assertTrue(adaptive["fallback_used"])
        self.assertLess(adaptive["confidence"], 0.5)


if __name__ == "__main__":
    unittest.main()
