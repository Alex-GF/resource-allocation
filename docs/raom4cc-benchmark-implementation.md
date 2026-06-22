# RAOM4CC Benchmark: Implementation and Adaptations for Pricing-Driven Resource Allocation

This document provides a comprehensive technical description of how the offloading algorithms from *Resource Allocation Optimization Model for Computing Continuum* (RAOM4CC) were implemented and adapted to serve as heuristic baselines in the pricing-driven resource allocation benchmark.

## 1. Introduction

The pricing-driven resource allocation framework solves a deployment-configuration problem: given a network topology, an aggregate resource demand vector, and a set of request constraints (budget, node count, device types, provider restrictions), select a set of infrastructure nodes that satisfies all constraints while minimizing total deployment cost. The optimization is delegated to PRIME, a constraint-solving engine exposed through a REST API.

To contextualize the performance of PRIME, it is necessary to compare it against established heuristics from the computing-continuum literature. The RAOM4CC paper proposes several offloading algorithms evaluated in a SUMO/PureEdgeSim simulation environment. These algorithms address a related but structurally different problem — namely, the assignment of individual tasks to computing layers in a mobile-edge continuum. Nevertheless, their core decision logic (layer preference, delay estimation, energy awareness, bin-packing) provides a rich set of heuristic strategies that can be repurposed as candidate-ordering policies for the pricing-driven benchmark.

This document details the implementation of nine such baselines, the conceptual mappings between the two problem domains, and the feasibility-aware placement mechanism that ensures a fair comparison against PRIME.

## 2. Background: RAOM4CC Formulations

### 2.1 Computing Continuum Layers

RAOM4CC organizes the computing continuum into three layers:

- **Mist** — resource-constrained devices at the network edge (e.g., IoT sensors, mobile devices).
- **Edge** — intermediary compute nodes (e.g., edge servers, access points) that serve as Compute Access Points (CAPs).
- **Cloud** — remote data-centers with abundant processing capacity.

Each layer offers different trade-offs in terms of processing latency, energy consumption, and available resources.

### 2.2 Task Model

A task $t$ is characterized by:

| Parameter | Symbol | Description |
|-----------|--------|-------------|
| CPU workload | $\mathrm{cpu\_mi}$ | Computation intensity in million instructions |
| Input size | $S_{\mathrm{in}}$ | Data volume to upload (bytes) |
| Output size | $S_{\mathrm{out}}$ | Data volume to download (bytes) |
| Required cores | $r$ | Number of CPU cores needed |
| Latency constraint | $\delta$ | Maximum tolerable end-to-end delay (seconds) |

### 2.3 Original Algorithms

The RAOM4CC paper defines seven primary algorithms:

- **Algorithm 1 (OneLayer):** Assigns a task to a fixed layer — mist (local), edge (CAP), or cloud.
- **Algorithm 2 (RoundRobin):** Cycles through available layers in round-robin fashion per origin node.
- **Algorithm 3 (DelayHeuristics):** Selects the layer with the smallest estimated delay.
- **Algorithm 4 (DelayEnergyHeuristics):** Minimizes a weighted cost combining delay ratio and energy ratio, modulated by battery depletion.
- **Algorithm 5 (BestFit):** Selects the fullest edge node that can still accommodate the task (bin-packing).
- **Algorithm 6 (BestFitDelay):** Applies the delay heuristic; if mist is preferred, keeps local execution; otherwise falls back to BestFit.
- **Algorithm 7 (BestFitDelayEnergy):** Same logic as Algorithm 6, but using the delay-energy cost function.

### 2.4 Key Equations

#### Delay Estimation (Equations 8–9)

The estimated delay for offloading a task $t$ to layer $l$ is a weighted sum of three components:

$$
\mathrm{delay}(t, l) = w_p \cdot d_{\mathrm{proc}} + w_n \cdot d_{\mathrm{net}} + w_q \cdot d_{\mathrm{queue}}
$$

where:

- $d_{\mathrm{proc}} = \frac{\mathrm{cpu\_mi}}{\mathrm{MIPS}_l}$ — processing delay, determined by the node's processing capacity.
- $d_{\mathrm{net}} = \frac{S_{\mathrm{in}} + S_{\mathrm{out}}}{B_l} + L_l$ — network delay, comprising transmission time over bandwidth $B_l$ and propagation latency $L_l$.
- $d_{\mathrm{queue}} = \frac{Q_l}{\mu_l} + L_{q,l}$ — queue delay, based on the node's queue length $Q_l$, service rate $\mu_l$, and any additional link-level queue delay.

The weights $(w_p, w_q, w_q)$ default to $\frac{1}{3}$ each and sum to 1.

#### Energy Estimation (Equations 10–12)

The energy consumed by offloading task $t$ to layer $l$ comprises CPU dynamic energy and, for non-mist layers, network transfer energy:

$$
\mathrm{energy}(t, l) = E_{\mathrm{CPU}}(l) + E_{\mathrm{link}}(t, l)
$$

where:

- $E_{\mathrm{CPU}}(l) = \frac{\mathrm{cpu\_mi}}{\mathrm{MIPS}_l} \cdot (P_{\mathrm{peak}} - P_{\mathrm{idle}})$ — dynamic energy from CPU computation.
- $E_{\mathrm{link}}(t, l) = e_{\mathrm{up}} \cdot S_{\mathrm{in}} + e_{\mathrm{down}} \cdot S_{\mathrm{out}} + e_{\mathrm{fixed}}$ — energy for network transfers (zero for mist layer).

#### Delay-Energy Cost Function (Algorithm 4)

The combined cost function used by Algorithm 4 is:

$$
\mathrm{cost}(l) = \alpha \cdot \mathrm{depletion} \cdot \frac{E_l}{E_{\min}} + \frac{d_l}{d_{\min}}
$$

where $E_{\min}$ and $d_{\min}$ are the minimum energy and delay across all candidate layers, $\alpha$ is a configurable scaling factor (default 1.0), and $\mathrm{depletion} = 1 - \mathrm{battery\_ratio}$ represents the battery depletion factor of the origin node.

## 3. Problem Mismatch and Adaptation Strategy

### 3.1 Structural Differences

The RAOM4CC algorithms and the pricing-driven benchmark solve fundamentally different problems:

| Aspect | RAOM4CC | Pricing-Driven |
|--------|---------|----------------|
| Input | Single task + origin node | Aggregate demand vector + topology |
| Decision | Assign one task to one layer/node | Select a set of $k$ nodes |
| Objective | Minimize delay or energy (varies) | Minimize deployment cost subject to constraints |
| Constraints | Task latency, battery | Budget, node count, resource coverage, provider types |
| Environment | SUMO mobility traces, PureEdgeSim | Static topology from EUA dataset |

### 3.2 Adaptation Principle

Rather than forcing the RAOM4CC algorithms to produce a single-node assignment (which would not solve the pricing-driven problem), the adaptation repurposes each algorithm as a **candidate-ordering policy**. The heuristics define an order in which nodes are considered; a subsequent feasibility-aware placement builder then greedily selects nodes from this ordered list until all demand constraints are satisfied.

This approach preserves the decision identity of each RAOM4CC heuristic (e.g., delay-heuristic still favors low-latency layers) while producing multi-node deployments that can be evaluated under the same objective used by PRIME: satisfy all request constraints at minimum cost.

### 3.3 Common Evaluation Objective

All baselines — RAOM4CC heuristics and PRIME alike — are evaluated under a single objective:

> Minimize total deployment cost while satisfying resource demand, node-count bound, budget bound, and provider/device-type constraints.

Delay and energy are retained as diagnostic metrics in the output but do not influence the feasibility or cost assessment of a deployment.

## 4. Conceptual Mapping

The following table maps RAOM4CC concepts to their pricing-driven equivalents:

| RAOM4CC Concept | Pricing-Driven Equivalent | Notes |
|-----------------|--------------------------|-------|
| `OrchestrationContext` | Topology DataFrame (`devices.csv`) | Built via `build_context_from_topology()` |
| `Task` | Aggregate request vector | Constructed from `filter_usageLimits_*` columns |
| `origin_node_id` | Nearest mist node (lowest queue) | Proxy for user location |
| `Node.layer` | `global_group` (1→mist, 2→edge, 3→cloud) | Mapped during context construction |
| `Node.metadata.resources` | `available_*` columns in topology | CPU, RAM, storage, GPU, TPU |
| `Node.metadata.unit_prices` | `unit_price_available_*` columns | Per-resource unit costs |
| `NetworkLink` | Default link (125 Mbps) | No SUMO traces; defaults used |
| Single-node selection | Multi-node greedy deployment | `_build_deployment()` |

## 5. Algorithm-by-Algorithm Adaptation

Each algorithm produces an **ordered list of candidate nodes** via `_candidate_order()`. The placement builder then iterates through this list, selecting nodes greedily.

### 5.1 `one_layer_mist`

- **Ordering:** All mist-layer nodes that match the request's device-type and provider constraints, sorted by unit cost then node ID.
- **RAOM4CC analog:** Algorithm 1 with layer = mist. In the original paper, this corresponds to local execution on the user device.
- **Expected behavior:** Rarely produces feasible deployments for large demands, as mist nodes have limited resources.

### 5.2 `one_layer_edge`

- **Ordering:** All edge-layer nodes matching request constraints, sorted by unit cost then node ID.
- **RAOM4CC analog:** Algorithm 1 with layer = edge (CAP assignment).
- **Expected behavior:** Often cost-effective for moderate demands; limited by per-node capacity.

### 5.3 `one_layer_cloud`

- **Ordering:** All cloud-layer nodes matching request constraints, sorted by unit cost then node ID.
- **RAOM4CC analog:** Algorithm 1 with layer = cloud.
- **Expected behavior:** High resource availability but typically higher cost.

### 5.4 `round_robin`

- **Ordering:** Nodes interleaved across available layers in round-robin fashion (e.g., mist₁, edge₁, cloud₁, mist₂, edge₂, ...). Within each layer, nodes are sorted by unit cost.
- **RAOM4CC analog:** Algorithm 2, which cycles through layers per origin node.
- **Expected behavior:** Balanced selection across layers; may produce diverse deployments.

### 5.5 `delay_heuristics`

- **Ordering:** Layers ranked by estimated delay (computed via Equations 8–9), then nodes within each layer sorted by unit cost.
- **RAOM4CC analog:** Algorithm 3.
- **Note:** Since network links use defaults (no SUMO traces), delay estimation primarily reflects processing capacity differences across layers.

### 5.6 `delay_energy_heuristics`

- **Ordering:** Layers ranked by the delay-energy cost function (Equation with $\alpha = 1.0$), then nodes within each layer sorted by unit cost.
- **RAOM4CC analog:** Algorithm 4.
- **Note:** Battery depletion factor defaults to 0 (no `remaining_battery_ratio` in topology data), so the cost function reduces to the delay ratio alone.

### 5.7 `best_fit`

- **Ordering:** Edge nodes first, sorted by descending reserved cores (fullest first), then non-edge nodes as fallback.
- **RAOM4CC analog:** Algorithm 5, which prioritizes the fullest edge node that can fit the task.
- **Expected behavior:** Packs edge nodes aggressively before spilling to cloud.

### 5.8 `best_fit_delay`

- **Ordering:** If the delay heuristic selects mist (local execution), nodes are ordered with mist first followed by the best-fit edge order. Otherwise, pure best-fit ordering is used.
- **RAOM4CC analog:** Algorithm 6.
- **Expected behavior:** Combines delay awareness with bin-packing efficiency.

### 5.9 `best_fit_delay_energy`

- **Ordering:** Same logic as `best_fit_delay`, but using the delay-energy cost function to determine the preferred layer.
- **RAOM4CC analog:** Algorithm 7.
- **Expected behavior:** Energy-aware variant of the hybrid approach.

## 6. Representative Task Construction

Since the RAOM4CC algorithms operate on individual tasks rather than aggregate demand, the benchmark constructs a **representative task** from the scenario's aggregate request. This is handled by `representative_task_from_request()`.

### 6.1 Task Profiles

Task characteristics are drawn from Table 3 of the RAOM4CC paper, mapped to the application classes used in the pricing-driven benchmark:

| Application | Input (bytes) | Output (bytes) | CPU (MI) | Latency (s) |
|-------------|---------------|----------------|----------|-------------|
| health | 20,480 | 2,048 | 2,000 | 0.3 |
| robot | 20,480 | 2,048 | 2,000 | 0.3 |
| mixed_reality | 512,000 | 102,400 | 4,000 | 0.5 |
| vr | 512,000 | 102,400 | 4,000 | 0.5 |
| computer_vision | 204,800 | 40,960 | 12,000 | 1.5 |
| cctv | 204,800 | 40,960 | 12,000 | 1.5 |
| video | 204,800 | 40,960 | 12,000 | 1.5 |
| lidar | 204,800 | 40,960 | 12,000 | 1.5 |
| nlp | 512,000 | 20,480 | 20,000 | 2.5 |

### 6.2 Origin Node Selection

The origin node is chosen as the mist-layer node with the lowest queue length (and lexicographically smallest ID as tiebreaker). If no mist nodes exist, any node with the lowest queue is used. This serves as a proxy for the user's physical location.

### 6.3 CPU Workload Derivation

When a matching task profile exists, `cpu_mi` is taken directly from the profile. Otherwise, it defaults to:

$$
\mathrm{cpu\_mi} = r \times 1{,}000
$$

where $r$ is the number of CPU cores requested in the aggregate demand vector.

## 7. Feasibility-Aware Placement Builder

The function `_build_deployment()` converts an ordered list of candidate nodes into a concrete deployment. Its design prevents heuristics from producing trivially infeasible results.

### 7.1 Greedy Selection Loop

```
while slots remain AND demand is not fully covered:
    candidate = choose_next_node(remaining, demand, covered, ...)
    if candidate is None: break
    select candidate, update covered resources and total cost
```

### 7.2 Node Selection Rules (`_choose_next_node`)

The selection applies three tiers of logic:

1. **Filtering:** Only candidates whose available resource capacity contributes to uncovered demand are considered. Nodes that provide zero marginal contribution are skipped.

2. **Viability check:** Before selecting a candidate, the builder verifies that the remaining deployment slots can still cover the remaining demand when the candidate is included. If a candidate would make full coverage impossible (and a viable continuation exists), the candidate is skipped.

3. **Preference:**
   - Among candidates that complete coverage (i.e., after selection, all demand is met), the one with the lowest incremental unit cost is preferred.
   - Among candidates that do not complete coverage but preserve feasibility, the one with the earliest position in the heuristic ordering is preferred.
   - If no viable candidate exists, the candidate with the highest coverage gain and lowest cost is selected as a fallback.

### 7.3 Cost Computation

The cost of selecting a node is computed as:

$$
\mathrm{cost}(n) = \sum_{r \in \mathcal{R}} \mathrm{alloc}(n, r) \times \mathrm{unit\_price}(n, r)
$$

where $\mathrm{alloc}(n, r)$ is the amount of resource $r$ allocated from node $n$ (the minimum of the node's capacity and the remaining uncovered demand for $r$), and $\mathrm{unit\_price}(n, r)$ is the per-unit price of resource $r$ on node $n$.

### 7.4 Final Validation

After the greedy loop terminates, `_deployment_feasibility()` checks:

- All resource demands are covered within a numerical tolerance ($10^{-9}$).
- The number of selected nodes does not exceed `maxSubscriptionSize`.
- The total cost does not exceed the budget constraint.
- At least one node was selected.

The deployment is marked as feasible only if all conditions are satisfied. Infeasible deployments are retained in the output with their `feasible=False` flag and a human-readable `reason` field, enabling downstream analysis of failure modes.

## 8. Input Data Reuse

The RAOM4CC benchmark reuses the same artifacts generated for the PRIME evaluation:

- **Topology files:** `synthetic-dataset/synthetic-topologies/<topology_id>/devices.csv` — the same device-level topology used as input to PRIME's pricing model.
- **Request constraints:** Extracted from `results/results.csv` by parsing the `filter_*` columns (`filter_maxPrice`, `filter_maxSubscriptionSize`, `filter_features`, `filter_usageLimits_*`).
- **Scenario identifiers:** The `scenario_id` field links each benchmark row to its corresponding PRIME result and topology.

No SUMO mobility traces are generated or consumed. Network link parameters use default values (125 Mbps bandwidth, zero propagation latency), and battery levels are not considered.

## 9. Output Schema

Each baseline produces rows conforming to the `BenchmarkSelection` schema:

| Field | Type | Description |
|-------|------|-------------|
| `scenario_id` | str | Scenario identifier |
| `algorithm` | str | Heuristic name (e.g., `delay_heuristics`) |
| `status` | str | `COMPLETED` or `FAILED` |
| `selected_node` | str | List of selected node IDs |
| `selected_layer` | str | List of selected node layers |
| `objective` | str | Always `minimize_cost` |
| `time_seconds` | float | Execution wall-clock time |
| `estimated_delay_seconds` | float | Maximum delay across selected nodes |
| `estimated_energy_joules` | float | Sum of energy across selected nodes |
| `estimated_cost` | float | Total deployment cost |
| `feasible` | bool | Whether all constraints are satisfied |
| `reason` | str | Infeasibility reason (empty if feasible) |
| `selected_features` | str | Device types of selected nodes |
| `selected_resources` | str | Covered resource amounts |
| `topology_id` | str | Topology UUID (added by script runner) |

Results are persisted to `results/raom4cc_benchmark_results.csv` in append mode, without overwriting existing PRIME results.

## 10. Usage

### 10.1 Programmatic API

```python
import pricing_driven_resource_allocation as pdsa
import pandas as pd

devices = pd.read_csv("synthetic-dataset/synthetic-topologies/<id>/devices.csv", index_col=0)
request = {
    "usageLimits": {"available_ram_gb": 4, "available_cpu_cores": 2},
    "features": ["SENSOR", "COMPUTER"],
    "maxSubscriptionSize": 3,
    "maxPrice": 500,
}

rows = pdsa.algorithms.run_raom4cc_benchmark(
    scenario_id="small_devices_vr_5_0",
    topology_devices=devices,
    request=request,
    app="vr",
)

pdsa.algorithms.save_benchmark_results_to_csv(rows, "results")
```

### 10.2 Script-Based Execution

```bash
python scripts/run_raom4cc_benchmark.py \
    --results-csv results/results.csv \
    --topologies-dir synthetic-dataset/synthetic-topologies \
    --output results/raom4cc_benchmark_results.csv
```

The script iterates over all scenarios in the PRIME results CSV, reconstructs each request, loads the corresponding topology, and runs all nine baselines.
