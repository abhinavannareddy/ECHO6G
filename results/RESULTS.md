# Example benchmark results

This table comes from the built-in benchmark with seed `2026` and 10,000 generated scenarios. It compares four strategies using the project's simplified formulas. It does not describe a real network.

To repeat the run, first build the C++ engine as described in the README, then run:

```powershell
python -m echo6g.cli --output results --seed 2026 --scenarios 10000
```

Each strategy is checked against the same 10,000 scenarios. A scenario passes only if both its delay and reliability targets are met.

| Strategy | Scenarios meeting both targets | Average delay | Average relative energy score | Adaptive fallback use |
|---|---:|---:|---:|---:|
| Energy saver | 16.49% | 47.476 ms | 2.698 | 0% |
| Fixed middle | 16.65% | 47.372 ms | 2.905 | 0% |
| Performance first | 33.92% | 26.366 ms | 7.938 | 0% |
| ECHO adaptive | 33.89% | 26.454 ms | 7.367 | 32.79% |

In this run, ECHO adaptive met both targets almost as often as Performance first. Its average relative energy score was about 7.2% lower. It used its fallback rule in about one third of the examples.

These numbers describe only the generated examples and the formulas in this project. They do not predict service quality or savings on real equipment. The energy score is not a measurement of power, cost, or carbon.
