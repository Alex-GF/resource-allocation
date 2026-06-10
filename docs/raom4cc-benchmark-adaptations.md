# RAOM4CC Algorithm Adaptations for the Pricing-Driven Benchmark

This note documents how the offloading algorithms from *Resource Allocation Optimization Model for Computing Continuum* (RAOM4CC) were adapted so they can be used as baselines in the benchmarking workflow of *Pricing-Driven Resource Allocation in the Computing Continuum*.

## Motivation

The original RAOM4CC algorithms were designed for task offloading in a simulated computing-continuum environment. Their decisions are based on layers, task origin, CAP assignment, delay estimates, energy estimates, and edge-node packing. By contrast, the pricing-driven benchmark evaluates a deployment-configuration problem: given a topology, an aggregate demand vector, and request constraints, find a set of infrastructure nodes that satisfies the constraints while minimizing deployment cost.

Using the RAOM4CC algorithms without adaptation would make the comparison methodologically weak, because the algorithms would optimize different criteria from PRIME. For this reason, the RAOM4CC algorithms are used as heuristic candidate-ordering policies, while every generated deployment is evaluated with the same benchmark objective used in the pricing-driven paper.

## Common Objective

All adapted RAOM4CC baselines are evaluated under the same objective:

> satisfy the request constraints and minimize deployment cost.

The benchmark rows explicitly report:

- `objective = "minimize_cost"`
- selected node configuration
- selected computing layers
- feasibility
- estimated deployment cost
- covered resources
- estimated delay
- estimated energy
- execution time

Delay and energy are retained as diagnostic metrics, but they are not used as the final comparison objective against PRIME.

## Adapted Interpretation of Each Algorithm

The original algorithms are preserved as policy names, but their output is adapted from a single offloading node into an ordered list of candidate nodes:

- `one_layer_mist`: considers mist nodes first.
- `one_layer_edge`: considers edge nodes first.
- `one_layer_cloud`: considers cloud nodes first.
- `round_robin`: interleaves candidates across the available layers.
- `delay_heuristics`: orders layers by estimated delay and then selects candidates within those layers.
- `delay_energy_heuristics`: orders layers by the RAOM4CC delay-energy cost function, then selects candidates within those layers.
- `best_fit`: prioritizes edge nodes using a packing-oriented order, then falls back to non-edge candidates.
- `best_fit_delay`: applies the delay heuristic as a local preference and otherwise uses BestFit ordering.
- `best_fit_delay_energy`: applies the delay-energy heuristic as a local preference and otherwise uses BestFit ordering.

## Feasibility-Aware Placement

A direct heuristic ordering can easily produce non-feasible deployments by spending the limited `maxSubscriptionSize` on nodes that do not cover the remaining demand. To avoid unfairly weak baselines, the adapted placement builder is feasibility-aware:

1. It skips candidates that do not contribute to any pending resource demand.
2. Before selecting a candidate, it checks whether the remaining deployment slots can still cover the remaining resource demand.
3. If a candidate would make coverage impossible while another feasible continuation exists, the candidate is skipped.
4. If multiple candidates complete the deployment, the lowest incremental unit-cost candidate is preferred.
5. The final deployment is marked feasible only if it satisfies the aggregate resource demand, node-count bound, budget bound, and requested node types/providers.

This keeps the heuristic identity while making the comparison against PRIME meaningful.

## Input Data Reuse

The adapted benchmark reuses the same artifacts as the PRIME evaluation:

- topology `devices.csv` files from `synthetic-dataset/synthetic-topologies/<topology_id>/`
- request/filter constraints already recorded in `results/results.csv`
- scenario identifiers and topology identifiers emitted by `evaluation.ipynb`

No SUMO traces are generated or used.

## Output

The RAOM4CC benchmark is written to a separate CSV file, `results/raom4cc_benchmark_results.csv`, or to a timestamped variant if that file already exists. Existing PRIME results are not overwritten.
