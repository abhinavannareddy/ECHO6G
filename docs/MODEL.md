# How the simulator works

ECHO-6G uses simple formulas to compare network resource strategies. It is an example program. It does not copy how a real radio network works in full, and its results have not been checked against network equipment.

## Information you enter

Each scenario has four values:

- **Traffic** — the amount of data the service needs, in modelled Mbps.
- **Channel quality** — a value from `0.25` to `1.0`. A higher value means a better channel in this model.
- **Delay limit** — the longest delay the service can accept, in milliseconds.
- **Reliability target** — the required chance of successful service. For example, `0.95` means 95%.

The web form accepts traffic from 0 to 10,000 Mbps, channel quality from 0.25 to 1, a delay limit above 0 and up to 10,000 ms, and a reliability target from 0.01 to 1.

## Resource levels

The simulator offers four resource levels. Level 1 assigns the fewest resources; level 4 assigns the most. These levels are examples. They do not represent Ericsson equipment, radio units, or a real network configuration.

The model estimates capacity with this formula:

```text
capacity = resource level × 38 × channel quality
```

The `38` is a made-up value used by the example model. The simulator serves up to the estimated capacity. If traffic is above that amount, it counts the extra traffic as overload. More overload and lower channel quality increase estimated delay and reduce estimated reliability.

The formulas and limits are in [`echo6g/native/engine.cpp`](../echo6g/native/engine.cpp). The model engine is written in C++17. The web page passes values to this same engine for both live comparisons and benchmarks.

## Delay, reliability, and energy

- **Delay** starts at 8 ms in the model. Overload and poor channel quality add to it.
- **Reliability** is estimated from overload and channel quality. The result is capped between 50% and 99.9%.
- **Energy** rises as the resource level increases. The number is a relative score created by a formula; it is not watts, kilowatt-hours, a utility bill, or a carbon estimate.

The page marks an option as meeting its targets only when both its estimated delay and estimated reliability pass the values you entered.

## The four strategies

- **Energy saver** picks a low resource level based on traffic alone.
- **Fixed middle** always picks level 2.
- **Performance first** always picks level 4.
- **ECHO adaptive** learns from generated examples, then chooses a level using the scenario values. If it sees values outside its training range, it uses a fallback rule and marks that choice in the results.

The web app recommends the option with the lowest estimated energy score among those that meet both targets. If none meet both targets, the app says so and shows the option with the highest model score for review. This is not a promise that the option will work on a real network.

## Benchmark

The benchmark creates repeatable example scenarios from a random seed in the C++ engine. It compares all four strategies against the same scenarios and reports:

- **SLA success rate** — the share of scenarios where both the delay and reliability targets were met. SLA means service-level agreement.
- **Mean latency** — the average estimated delay.
- **Mean energy units** — the average relative energy score.
- **Mean reward** — the model's score for balancing service targets and energy.
- **Fallback rate** — how often ECHO adaptive used its fallback rule.

These values describe only the generated examples and these formulas. They do not predict results for a specific carrier, location, customer, or product.

## Limits

Do not use this simulator as the only basis for a purchase or deployment. It has no Ericsson product list or pricing, and it does not model real radio propagation, interference, 3GPP requirements, hardware performance, power use, or operating cost. Check plans with the equipment supplier and measured network data before making decisions.
