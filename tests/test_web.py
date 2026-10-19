import csv
from collections import Counter, defaultdict
from http.server import ThreadingHTTPServer
import math
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Thread
from urllib.request import urlopen
import unittest

from echo6g.benchmark import run_benchmark
from echo6g.web import DecisionHandler, evaluate_scenario


class WebAndBenchmarkTests(unittest.TestCase):
    def test_buyer_evaluation_returns_four_comparable_options(self):
        result = evaluate_scenario({
            "traffic_mbps": 85,
            "channel_quality": 0.82,
            "latency_budget_ms": 35,
            "reliability_target": 0.93,
        })

        self.assertEqual(len(result["options"]), 4)
        self.assertEqual(
            {option["policy_name"] for option in result["options"]},
            {"energy_saver", "fixed_middle", "performance_first", "echo_adaptive"},
        )
        self.assertIn(result["recommendation"]["status"], {"meets_sla", "no_fit"})
        self.assertEqual(result["scenario"]["traffic_mbps"], 85)
        self.assertTrue(all(option["energy_units"] > 0 for option in result["options"]))
        if result["recommendation"]["status"] == "meets_sla":
            selected = next(option for option in result["options"]
                            if option["policy_name"] == result["recommendation"]["policy"])
            self.assertTrue(selected["sla_met"])

    def test_buyer_evaluation_rejects_invalid_inputs(self):
        invalid_values = [
            ("traffic_mbps", -1),
            ("traffic_mbps", 10_001),
            ("channel_quality", 1.01),
            ("latency_budget_ms", 0),
            ("latency_budget_ms", 10_001),
            ("reliability_target", 1.1),
            ("reliability_target", 0.001),
            ("traffic_mbps", math.inf),
            ("traffic_mbps", math.nan),
        ]
        base = {
            "traffic_mbps": 85,
            "channel_quality": 0.82,
            "latency_budget_ms": 35,
            "reliability_target": 0.93,
        }
        for field, value in invalid_values:
            with self.subTest(field=field, value=value):
                scenario = {**base, field: value}
                with self.assertRaises(ValueError):
                    evaluate_scenario(scenario)

    def test_buyer_evaluation_rejects_missing_inputs(self):
        with self.assertRaisesRegex(ValueError, "Missing required fields"):
            evaluate_scenario({"traffic_mbps": 85})

    def test_benchmark_rejects_empty_or_oversized_runs(self):
        with self.assertRaisesRegex(ValueError, "between 1 and 10000"):
            run_benchmark("unused-output", n=0)
        with self.assertRaisesRegex(ValueError, "between 1 and 10000"):
            run_benchmark("unused-output", n=10_001)

    def test_full_generated_dataset_has_valid_results_for_every_strategy(self):
        with TemporaryDirectory(prefix="echo6g-benchmark-") as output_dir:
            outcomes, summaries = run_benchmark(output_dir, seed=2026, n=10_000)
            self.assertEqual(len(outcomes), 40_000)
            self.assertEqual(len(summaries), 4)
            self.assertEqual(
                {summary["policy"] for summary in summaries},
                {"energy_saver", "fixed_middle", "performance_first", "echo_adaptive"},
            )

            counts = Counter(row["policy_name"] for row in outcomes)
            self.assertEqual(set(counts.values()), {10_000})
            by_scenario = defaultdict(list)
            for row in outcomes:
                by_scenario[row["scenario_name"]].append(row)
                self.assertTrue(math.isfinite(float(row["latency_ms"])))
                self.assertTrue(math.isfinite(float(row["reliability"])))
                self.assertGreater(float(row["energy_units"]), 0)
                self.assertGreaterEqual(float(row["reliability"]), 0.5)
                self.assertLessEqual(float(row["reliability"]), 0.999)
                expected_fit = (
                    float(row["latency_ms"]) <= float(row["latency_budget_ms"])
                    and float(row["reliability"]) >= float(row["reliability_target"])
                )
                self.assertEqual(row["sla_met"] == "true", expected_fit)

            self.assertEqual(len(by_scenario), 10_000)
            self.assertTrue(all(len(rows) == 4 for rows in by_scenario.values()))
            self.assertTrue((Path(output_dir) / "benchmark_summary.csv").is_file())

            with (Path(output_dir) / "benchmark_results.csv").open(
                newline="", encoding="utf-8"
            ) as source:
                exported_rows = list(csv.DictReader(source))
            self.assertEqual(len(exported_rows), 40_000)
            self.assertIn("latency_budget_ms", exported_rows[0])
            self.assertIn("reliability_target", exported_rows[0])

    def test_web_serves_page_and_image_assets(self):
        server = ThreadingHTTPServer(("127.0.0.1", 0), DecisionHandler)
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            for path, content_type, marker in [
                ("/", "text/html", b"Compare network options"),
                ("/network-illustration.svg", "image/svg+xml", b"Network scenario comparison"),
                ("/favicon.svg", "image/svg+xml", b"<svg"),
            ]:
                with self.subTest(path=path):
                    with urlopen(f"http://127.0.0.1:{server.server_port}{path}", timeout=2) as response:
                        self.assertEqual(response.status, 200)
                        self.assertIn(content_type, response.headers["Content-Type"])
                        self.assertIn(marker, response.read())
        finally:
            server.shutdown()
            thread.join(timeout=2)
            server.server_close()


if __name__ == "__main__":
    unittest.main()
