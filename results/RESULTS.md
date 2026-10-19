# Example benchmark results

These results come from the built-in example run. They do not describe a real Ericsson network or any other real network.

To repeat the run, use:

```powershell
python -m echo6g.cli --output results --seed 2026 --scenarios 160
```

The program creates 160 example scenarios and tests all four strategies against them. A scenario counts as a pass only when the strategy meets both the delay and reliability targets.

| Strategy | Scenarios meeting both targets | Average delay | Average relative energy score | Adaptive fallback use |
|---|---:|---:|---:|---:|
| Energy saver | 21.25% | 44.730 ms | 2.692 | 0% |
| Fixed middle | 21.25% | 44.684 ms | 2.897 | 0% |
| Performance first | 34.38% | 24.747 ms | 7.915 | 0% |
| ECHO adaptive | 34.38% | 24.776 ms | 7.334 | 35.63% |

In this run, ECHO adaptive met both targets as often as Performance first. Its average relative energy score was about 7.3% lower. It used its fallback rule in about 36% of scenarios. That rule makes a cautious choice when a scenario is outside the examples used to train the strategy.

These comparisons show only how the four strategies behave under the project's formulas. They are not evidence of savings or service quality on real equipment. The energy score is not a measurement of power, cost, or carbon.
