import unittest

from echo6g.web import evaluate_scenario


class NativeModelTests(unittest.TestCase):
    def test_model_reports_finite_metrics_for_all_strategies(self):
        result = evaluate_scenario({
            "traffic_mbps": 40,
            "channel_quality": 0.9,
            "latency_budget_ms": 30,
            "reliability_target": 0.90,
        })
        self.assertEqual(len(result["options"]), 4)
        for option in result["options"]:
            with self.subTest(policy=option["policy_name"]):
                self.assertGreaterEqual(option["throughput_mbps"], 0)
                self.assertGreaterEqual(option["reliability"], 0)
                self.assertLessEqual(option["reliability"], 1)
                self.assertGreater(option["energy_units"], 0)
                self.assertIn(option["resource_level"], (1, 2, 3, 4))


if __name__ == "__main__":
    unittest.main()
