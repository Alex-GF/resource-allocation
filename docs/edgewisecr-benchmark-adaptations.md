# EdgeWiseCR Benchmark: Implementation and Adaptations for Pricing-Driven Resource Allocation

This document describes how the EdgeWiseCR methodology — originally presented in *Combining Declarative and Linear Programming for Application Management in the Cloud-Edge Continuum* (Massa et al., Future Generation Computer Systems, 2025) — was adapted to serve as a baseline in the pricing-driven resource allocation benchmark.

## 1. Introduction

EdgeWiseCR is a hybrid placement methodology that combines declarative programming (Prolog) with Mixed-Integer Linear Programming (MILP) to solve the data-aware multi-service application placement problem in Cloud-Edge settings. The original implementation relies on SWI-Prolog for constraint filtering and OR-Tools' SCIP solver for optimisation, orchestrated by the ECLYPSE simulation framework.

The pricing-driven benchmark evaluates a structurally different problem: given a topology, an aggregate resource demand vector, and request constraints (budget, node count, device types, providers), select a set of infrastructure nodes that satisfies all constraints while minimising deployment cost. To enable a meaningful comparison, the EdgeWiseCR algorithmic cores (MILP placement and greedy bin-packing heuristic) were ported to plain Python, preserving their decision identity while operating on the same topology and request artifacts used by PRIME and the RAOM4CC baselines.

## 2. Background: EdgeWiseCR Methodology

### 2.1 Original Architecture

EdgeWiseCR operates in two stages:

1. **Declarative stage (Prolog):** Pre-filters compatible `(component, node)` pairs based on software, hardware, architecture, security, and QoS constraints. Computes per-pair deployment costs via `cost/3` predicates. This stage also implements Continuous Reasoning (CR), which reuses prior placements to reduce recomputation and service migration across simulation ticks.

2. **MILP stage (OR-Tools SCIP):** Solves a bin-packing optimisation problem — one binary variable per `(component, node)` pair, one bin variable per node — minimising total cost subject to hardware capacity, bandwidth, latency, and budget constraints.

### 2.2 Evaluated Configurations

The paper evaluates six configurations, arising from the combination of three binary flags:

| Configuration | Declarative | Preprocess | CR |
|---------------|-------------|------------|-----|
| `edgewise` | No (MILP) | Yes | No |
| `edgewise_cr` | No (MILP) | Yes | Yes |
| `edgewise_num` | No (MILP) | No | No |
| `prolog` | Yes (greedy) | Yes | No |
| `prolog_cr` | Yes (greedy) | Yes | Yes |
| `prolog_num` | Yes (greedy) | No | No |

When the declarative flag is set, the pure-Prolog greedy heuristic (`binpack.pl`) is used instead of the MILP solver. The `preprocess` flag controls whether the declarative stage filters compatible nodes before optimisation. The `cr` flag enables Continuous Reasoning.

### 2.3 MILP Formulation (Original)

The original MILP defines:

- $x_{ij} \in \{0,1\}$: component $i$ placed on node $j$
- $b_j \in \{0,1\}$: node $j$ used (bin variable)
- $C_{ij}$: cost of placing component $i$ on node $j$

**Constraints:**

- Each component on exactly one node: $\sum_j x_{ij} = 1 \;\forall i$
- Hardware capacity: $\sum_i \text{HW}_i \cdot x_{ij} \leq \text{HW}_j - \text{hwTh} \;\forall j$
- Budget linking: $x_{ij} \leq b_j \;\forall i,j$
- Node budget: $\sum_j b_j \leq S$ (number of components)
- Bandwidth and latency constraints per data flow

**Objective:** $\min \sum_{i,j} C_{ij} \cdot x_{ij}$

### 2.4 Greedy Heuristic (binpack.pl)

The pure-Prolog variant uses a greedy bin-packing strategy:

1. Rank components by hardware requirements (ascending).
2. For each component, find compatible nodes sorted by descending hardware capacity ($1/\text{HWCaps}$).
3. Prefer placing on already-used nodes (bin-packing); otherwise open a new node.
4. Enforce budget as the sum of maximum per-component costs.
5. Validate QoS (latency, bandwidth, security) on the final placement.

## 3. Problem Mismatch and Adaptation Strategy

### 3.1 Structural Differences

| Aspect | EdgeWiseCR | Pricing-Driven |
|--------|-----------|----------------|
| Application | Multi-service DAG with data flows | Aggregate resource demand vector |
| Selection | One component → exactly one node | Pool of nodes covering aggregate demand |
| Cost | Per-(component,node) SW+HW cost | Per-resource unit_price × allocated amount |
| Constraints | HW, BW, latency, security, budget | Resource coverage, max nodes, budget, device types, providers |
| Topology | Prolog facts + networkx graph | CSV DataFrame (geographic) |
| Simulation | ECLYPSE dynamic simulation (Ray Tune) | Static benchmark (single tick) |

### 3.2 Adaptation Principle

Following the same methodology used for the RAOM4CC baselines, the EdgeWiseCR algorithms are adapted by:

1. **Preserving the algorithmic cores:** The MILP formulation and greedy bin-packing heuristic are retained as the two placement engines.
2. **Replacing the declarative stage:** The Prolog-based compatibility filter is replaced by a Python filter that enforces device-type, provider, and non-zero-capacity constraints. This is equivalent because the pricing-driven problem has no software, architecture, security, or data-flow constraints.
3. **Adapting the formulation:** The MILP variables are redefined from per-component assignment to per-resource allocation, matching the aggregate-demand structure of the pricing-driven problem.
4. **Common evaluation objective:** All variants are evaluated under `minimize_cost`, the same objective used by PRIME and RAOM4CC.

### 3.3 Continuous Reasoning in the Static Benchmark

In the original ECLYPSE simulation, CR reuses the previous tick's placement to skip unchanged components and reduce migrations. In the static pricing-driven benchmark there is a single tick, so CR has no effect on the placement decision. The `cr` flag is retained for variant naming consistency and reports `moved_services = 0`.

## 4. Adapted MILP Formulation

### 4.1 Variables

- $b_j \in \{0,1\}$: device $j$ selected (bin variable)
- $a_{jr} \in [0, c_{jr}]$: amount of resource $r$ allocated from device $j$ (continuous)

where $c_{jr}$ is the capacity of device $j$ for resource $r$.

### 4.2 Constraints

**Linking (allocation only from selected nodes):**

$$a_{jr} \leq c_{jr} \cdot b_j \;\forall j, r$$

**Demand coverage:**

$$\sum_j a_{jr} \geq d_r \;\forall r$$

where $d_r$ is the aggregate demand for resource $r$.

**Maximum nodes (subscription size):**

$$\sum_j b_j \leq K$$

where $K$ is `maxSubscriptionSize`.

**Budget:**

$$\sum_{j,r} p_{jr} \cdot a_{jr} \leq B$$

where $p_{jr}$ is the unit price of resource $r$ on device $j$, and $B$ is `maxPrice`.

### 4.3 Objective

$$\min \sum_{j,r} p_{jr} \cdot a_{jr}$$

This formulation preserves the bin-packing structure of the original EdgeWise MILP (binary selection variables $b_j$) while replacing the per-component assignment with per-resource allocation, which matches the aggregate-demand structure of the pricing-driven problem.

## 5. Adapted Greedy Heuristic

The Python port of `binpack.pl` follows the same greedy logic:

1. **Rank resources by hardness:** Resources are sorted by ascending number of covering nodes (scarcest first).
2. **Rank nodes by capacity:** Nodes are sorted by descending total capacity across demanded resources, mirroring the $1/\text{HWCaps}$ ordering in `lightNodeOK`.
3. **Greedy assignment:** For each resource, iterate over nodes preferring already-selected nodes (bin-packing) before opening new ones. Allocate the minimum of remaining demand and node capacity.
4. **Budget enforcement:** Skip allocations that would exceed the budget.
5. **Max-nodes enforcement:** Do not open new nodes once `maxSubscriptionSize` is reached.
6. **Feasibility check:** The final placement is feasible only if all resource demands are covered, node-count and budget constraints are satisfied.

## 6. Variant-by-Variant Description

### 6.1 `edgewise` (MILP, preprocess=True, cr=False)

The declarative filter retains only nodes matching the request's device types, providers, and having non-zero capacity for at least one demanded resource. The MILP then solves the adapted formulation to optimality.

### 6.2 `edgewise_cr` (MILP, preprocess=True, cr=True)

Identical to `edgewise` in the static benchmark. The CR flag records `moved_services = 0` since there is no previous placement to compare against.

### 6.3 `edgewise_num` (MILP, preprocess=False, cr=False)

No declarative pre-filtering: all topology nodes are forwarded to the MILP, which decides selection and allocation. This may increase solver time on large topologies but avoids excluding potentially useful nodes.

### 6.4 `prolog` (greedy, preprocess=True, cr=False)

The greedy bin-packing heuristic runs on the pre-filtered candidate set. This is the fastest variant but may produce suboptimal placements compared to the MILP.

### 6.5 `prolog_cr` (greedy, preprocess=True, cr=True)

Identical to `prolog` in the static benchmark, with `moved_services = 0`.

### 6.6 `prolog_num` (greedy, preprocess=False, cr=False)

The greedy heuristic runs on the full node set without pre-filtering.

## 7. Input Data Reuse

The EdgeWiseCR benchmark reuses the same artifacts as the PRIME and RAOM4CC evaluations:

- **Topology files:** `synthetic-dataset/synthetic-topologies/<topology_id>/devices.csv`
- **Request constraints:** Extracted from `results/results.csv` by parsing the `filter_*` columns
- **Scenario identifiers:** The `scenario_id` field links each benchmark row to its corresponding PRIME and RAOM4CC results

No ECLYPSE simulation, Ray Tune orchestration, or SWI-Prolog installation is required.

## 8. Output Schema

Each variant produces rows conforming to the `EdgeWiseSelection` schema:

| Field | Type | Description |
|-------|------|-------------|
| `scenario_id` | str | Scenario identifier |
| `algorithm` | str | Variant name (e.g., `edgewise`) |
| `status` | str | `OPTIMAL`, `FEASIBLE`, `INFEASIBLE`, `TIMEOUT`, `COMPLETED`, or `FAILED` |
| `selected_node` | str | List of selected node IDs |
| `selected_layer` | str | List of selected node layers (mist/edge/cloud) |
| `objective` | str | Always `minimize_cost` |
| `time_seconds` | float | Solver wall-clock time |
| `estimated_cost` | float | Total deployment cost (allocation-based) |
| `feasible` | bool | Whether all constraints are satisfied |
| `bins` | int | Number of distinct nodes used |
| `moved_services` | int | CR metric (0 in static benchmark) |
| `reason` | str | Infeasibility reason (empty if feasible) |
| `selected_features` | str | Device types of selected nodes |
| `selected_resources` | str | Covered resource amounts |
| `topology_id` | str | Topology UUID (added by script runner) |

Results are persisted to `results/edgewisecr_results.csv` in append mode, without overwriting existing PRIME or RAOM4CC results.

## 9. Comparison with PRIME and RAOM4CC

For each `scenario_id`, the three result files can be joined to compare:

| Metric | `results.csv` (PRIME) | `raom4cc_benchmark_results.csv` | `edgewisecr_results.csv` |
|--------|----------------------|--------------------------------|--------------------------|
| Cost | `cost` | `estimated_cost` | `estimated_cost` |
| Time | `time_seconds` | `time_seconds` | `time_seconds` |
| Feasibility | `status == COMPLETED` | `feasible` | `feasible` |
| Nodes selected | `add_ons` | `selected_node` | `selected_node` |

**Note on cost comparability:** PRIME uses a subscription-based cost model (charging for full node capacity upon selection), while the RAOM4CC and EdgeWiseCR baselines use an allocation-based cost model (charging only for the allocated portion of capacity). Direct cost comparison across models requires care; comparing the number of selected nodes and feasibility rates is more straightforward.

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

rows = pdsa.algorithms.run_edgewisecr_benchmark(
    scenario_id="small_devices_vr_5_0",
    topology_devices=devices,
    request=request,
    timeout_seconds=60,
)

pdsa.algorithms.save_edgewisecr_benchmark_results_to_csv(rows, "results")
```

### 10.2 Script-Based Execution

```bash
python scripts/run_edgewisecr_benchmark.py \
    --results-csv results/results.csv \
    --topologies-dir synthetic-dataset/synthetic-topologies \
    --output results/edgewisecr_results.csv \
    --timeout 60
```

Optional arguments:

- `--limit N`: Run only the first N scenarios (smoke testing)
- `--variants edgewise prolog`: Run a subset of variants
