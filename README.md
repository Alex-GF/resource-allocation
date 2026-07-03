# PROMISE: Pricing-driven Resource Allocation Method for Service Infrastructure Deployment — Laboratory Package

Deploying applications across the computing continuum requires selecting infrastructure nodes that jointly satisfy functional and non-functional constraints. As infrastructures grow in scale and heterogeneity, this resource allocation (RA) problem becomes inherently combinatorial and can be viewed as an instance of a configuration problem. Existing solutions, however, rely on ad-hoc formulations that hinder reuse and overlook constraints arising in multi-provider environments.

This paper instantiates the Configuration Problems framework for resource allocation by representing its configuration space as an iPricing, a model originally proposed for the Software-as-a-Service domain. This provides the first evidence supporting the hypothesis that a unified formulation would be enough to represent configuration problems across the continuum. Building on this, we present: (i) a pricing-based formulation of RA; (ii) \approachName, which leverages a pricing analysis engine to solve resource allocation in multi-provider environments; (iii) synthetic generation processes for infrastructure topologies and workload demands; and (iv) a benchmark comprising 9,600 precomputed RA scenarios.

This repository serves as an artifact accompanying the paper described above. It contains the code, datasets, and instructions necessary to reproduce the experiments and results presented in the paper.

> [!IMPORTANT]
> This laboratory package is submitted for artefact evaluation at **ICSOC**.

## Table of Contents

- [1. Repository Structure](#1-repository-structure)
- [2. Prerequisites](#2-prerequisites)
- [3. Installation](#3-installation)
- [4. Reproducing the Full Experiment](#4-reproducing-the-full-experiment)
  - [4.1 Stage I — Scenario Generation and PROMISE Optimisation](#41-stage-i--scenario-generation-and-promise-optimisation)
  - [4.2 Stage II — Baseline Execution](#42-stage-ii--baseline-execution)
  - [4.3 Stage III — Statistical Comparison](#43-stage-iii--statistical-comparison)
- [5. Reproducing the Comparison from Pre-Computed Results](#5-reproducing-the-comparison-from-pre-computed-results)
- [6. Using the Python Package](#6-using-the-python-package)
  - [6.1 `pdsa.dataset`](#61-pdsadataset)
  - [6.2 `pdsa.generators`](#62-pdsagenerators)
  - [6.3 `pdsa.utils`](#63-pdsautils)
  - [6.4 `pdsa.optimize`](#64-pdsaoptimize)
  - [6.5 `pdsa.algorithms`](#65-pdsaalgorithms)
- [7. Testing](#7-testing)
- [8. Documentation](#8-documentation)
- [9. Data and Outputs](#9-data-and-outputs)
- [10. License and Disclaimer](#10-license-and-disclaimer)

## 1. Repository Structure

```text
services-allocation/
├── config/
│   └── experiment_configuration.yml        # Scenario definitions (S/M/L × 4 apps × 2 axes)
├── docker-compose.yml                      # PRIME analysis engine (port 3000)
├── docs/
│   ├── results-discussion.md               # Per-technique analysis (17 techniques)
│   ├── results-discussion-grouped.md       # Per-group analysis (6 technique groups)
│   ├── raom4cc-benchmark-adaptations.md    # RAOM4CC adaptation notes
│   ├── raom4cc-benchmark-implementation.md # RAOM4CC implementation details
│   └── edgewisecr-benchmark-adaptations.md # EdgeWiseCR adaptation notes
├── evaluation.ipynb                        # End-to-end experimental pipeline (Stage I)
├── baseline_comparison.ipynb               # Statistical comparison notebook (Stage III)
├── eua-dataset/
│   ├── edge-servers/                       # Input edge-node datasets (Optus/Telstra/Vodafone)
│   └── users/                              # Input user-location datasets
├── iPricing/
│   ├── iPricing.proto                      # Pricing model schema (Protocol Buffers)
│   └── model/iPricing_pb2.py              # Generated Python protobuf module
├── pricing_driven_resource_allocation/     # Core Python package
│   ├── __init__.py                         # Package entry point (v1.0.0)
│   ├── optimize.py                         # PRIME REST API client and polling loop
│   ├── algorithms/
│   │   ├── benchmark.py                    # RAOM4CC benchmark adapter (9 variants)
│   │   ├── raom4cc.py                      # RAOM4CC offloading heuristics
│   │   ├── edgewisecr.py                   # EdgeWiseCR MILP + greedy engines
│   │   ├── edgewisecr_benchmark.py         # EdgeWiseCR benchmark adapter
│   │   └── msgdp.py                        # MS-GD-P genetic algorithm engine
│   ├── dataset/
│   │   ├── load.py                         # Dataset loading utilities
│   │   ├── transform.py                    # Filtering and resource assignment
│   │   └── save_results.py                 # Results persistence (CSV)
│   ├── generators/
│   │   ├── topology.py                     # Topology synthesis per scenario
│   │   ├── pricing.py                      # Pricing YAML generation
│   │   ├── problem_instance.py             # Request-constrained instance construction
│   │   ├── client_demand.py               # Demand modelling by application class
│   │   └── request.py                      # Request payload builder
│   └── utils/
│       ├── geometrical_utils.py            # Spatial computations (haversine, point-in-polygon)
│       └── yaml_utils.py                   # YAML ↔ protobuf conversion helpers
├── results/
│   ├── results.csv                         # PROMISE optimisation outcomes (9 600 scenarios)
│   ├── raom4cc_benchmark_results.csv       # RAOM4CC baseline results (9 variants)
│   ├── edgewisecr_results.csv              # EdgeWiseCR baseline results (6 variants)
│   ├── msgdp_benchmark_results.csv         # MS-GD-P baseline results (1 variant)
│   ├── _true_feasibility_pivot.csv         # Recomputed feasibility under full constraints
│   └── figures/                            # 32 publication-ready plots (PNG)
├── scripts/
│   ├── run_raom4cc_benchmark.py            # Execute RAOM4CC baselines over all scenarios
│   ├── run_edgewisecr_benchmark.py         # Execute EdgeWiseCR baselines over all scenarios
│   ├── run_msgdp_benchmark.py              # Execute MS-GD-P baseline over all scenarios
│   └── feasibility_under_constraints.py    # Recompute feasibility under provider exclusions
├── synthetic-dataset/
│   ├── data/                               # Source device and client datasets
│   └── synthetic-topologies/               # 9 600 generated topologies with pricing instances
├── tests/
│   ├── test_raom4cc_algorithms.py          # RAOM4CC unit tests
│   ├── test_edgewisecr_algorithms.py       # EdgeWiseCR unit tests
│   └── run_msgdp_algorithms.py             # MS-GD-P execution test
├── requirements.txt                        # Pinned Python dependencies
├── setup.py                                # Package installation (pip install -e .)
└── README.md
```

## 2. Prerequisites

| Requirement | Version | Purpose |
|:---|:---|:---|
| Python | ≥ 3.10 | Core runtime |
| Docker + Docker Compose | any recent | PRIME analysis engine container |
| Protocol Buffers compiler (`protoc`) | ≥ 3.19 | Regenerating `iPricing.proto` (optional) |
| Jupyter | ≥ 7.0 | Executing the experimental notebooks |

The experiment was validated on an Apple Silicon M4 Pro workstation with 24 GB of
main memory. The complete pipeline (Stages I–III) requires approximately ten hours
of uninterrupted execution.

## 3. Installation

```bash
git clone <repository-url>
cd services-allocation
python -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
pip install -e .
```

## 4. Reproducing the Full Experiment

The experiment is structured in three sequential stages. Stages are independent
once their input CSVs exist, but Stage I must complete before Stage II, and both
must complete before Stage III.

> [!WARNING]
> Stage I is computationally intensive and requires the PRIME Docker container.
> Stages II and III run without Docker and complete in minutes to hours.

### 4.1 Stage I — Scenario Generation and PROMISE Optimisation

This stage generates 9 600 synthetic topologies, constructs pricing models and
constrained problem instances, and invokes the PRIME constraint solver for each
scenario.

**Step 1. Verify port 3000 is available:**

```bash
lsof -i :3000
```

If any process is bound to port 3000, release it before continuing.

**Step 2. Start the PRIME analysis engine:**

```bash
docker-compose up -d
curl http://localhost:3000/health
```

The notebook expects PRIME at `http://localhost:3000/api/v1/`. If a different port
is used, update `PRIME_INSTANCE_URL` in the first cell of `evaluation.ipynb`.

**Step 3. Execute the pipeline notebook:**

```bash
jupyter notebook evaluation.ipynb
```

Execute all cells in order. The notebook performs:

1. Load and validate `config/experiment_configuration.yml`.
2. Load and preprocess the EUA edge dataset (devices, users, providers).
3. Generate 9 600 topology instances under `synthetic-dataset/synthetic-topologies/`.
4. Build pricing YAML files and request-constrained problem instances.
5. Submit each instance to PRIME via `pdsa.optimize(...)` and poll for completion.
6. Persist optimisation outcomes to `results/results.csv` and generate figures.

**Step 4. Stop the PRIME container:**

```bash
docker-compose down
```

**Output:** `results/results.csv` (9 600 rows × 30 columns) and 32 figures in
`results/figures/`.

### 4.2 Stage II — Baseline Execution

Three benchmark runner scripts execute the sixteen heuristic baselines over the
same 9 600 scenarios. Each script reads `results/results.csv` to recover scenario
metadata (topology IDs, resource demands, budget constraints) and writes its output
to a dedicated CSV.

**RAOM4CC (9 variants: 3 single-layer + 6 advanced):**

```bash
python scripts/run_raom4cc_benchmark.py
```

Output: `results/raom4cc_benchmark_results.csv`

**EdgeWiseCR (6 variants: 3 greedy + 3 MILP):**

```bash
python scripts/run_edgewisecr_benchmark.py
```

Output: `results/edgewisecr_results.csv`

**MS-GD-P (1 variant: priority-based genetic algorithm):**

```bash
python scripts/run_msgdp_benchmark.py
```

Output: `results/msgdp_benchmark_results.csv`

Each script accepts `--limit N` for smoke testing on the first N scenarios and
`--output PATH` to redirect output. Scenario-to-topology UUID mapping is extracted
automatically from `evaluation.ipynb` cell outputs.

### 4.3 Stage III — Statistical Comparison

The comparison notebook aggregates all four result CSVs, computes feasibility
under progressively stricter constraint readings, performs Kruskal-Wallis and
Mann-Whitney U tests, and generates publication-ready figures.

```bash
jupyter notebook baseline_comparison.ipynb
```

Execute all cells in order. The notebook produces:

- Feasibility heatmaps and bar charts (own model + full constraint set).
- Execution-time distributions and scalability plots.
- Node-selection profiles and cost-vs-node-count scatter plots.
- Boxplots of solution cost by technique group and application type.
- Summary statistics tables (per-technique and per-group).

**Output:** 32 PNG figures in `results/figures/` and printed statistical tables.

Detailed analysis of the results is provided in:

- [`docs/results-discussion.md`](docs/results-discussion.md) — per-technique analysis
  with summary metrics tables for all 17 techniques.
- [`docs/results-discussion-grouped.md`](docs/results-discussion-grouped.md) —
  per-group analysis with summary metrics tables for 6 technique groups.

## 5. Reproducing the Comparison from Pre-Computed Results

If the full experiment has already been executed (or the pre-computed CSVs are
provided as part of the artefact), Stages I and II can be skipped. The comparison
notebook reads directly from the result CSVs and does not require Docker or the
PRIME engine.

```bash
cd services-allocation
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e .
jupyter notebook baseline_comparison.ipynb
```

The notebook requires the following files to be present in `results/`:

| File | Rows | Description |
|:---|:---|:---|
| `results.csv` | 9 600 | PROMISE optimisation outcomes |
| `raom4cc_benchmark_results.csv` | 86 400 | RAOM4CC (9 variants × 9 600) |
| `edgewisecr_results.csv` | 57 600 | EdgeWiseCR (6 variants × 9 600) |
| `msgdp_benchmark_results.csv` | 9 600 | MS-GD-P (1 variant × 9 600) |

Additionally, `synthetic-dataset/synthetic-topologies/` must contain the 9 600
topology directories (each with `devices.csv` and `metadata.json`) for
post-hoc feasibility recomputation.

## 6. Using the Python Package

The package is imported as `pricing_driven_resource_allocation` (abbreviated `pdsa`
in code examples) and exposes five public namespaces:

```python
import pricing_driven_resource_allocation as pdsa

pdsa.dataset       # data loading and transformation
pdsa.generators    # topology, pricing, and problem-instance generation
pdsa.utils         # YAML ↔ protobuf conversion and spatial utilities
pdsa.optimize      # PRIME REST API client
pdsa.algorithms    # baseline algorithm implementations
```

### 6.1 `pdsa.dataset`

| Function | Description |
|:---|:---|
| `load_devices_dataframe(path)` | Loads the raw edge-device CSV and standardises column names. |
| `load_client_locations_dataframe(path)` | Loads and normalises client geolocation data. |
| `filter_devices_by_vendors(df, vendors)` | Filters devices by provider and adds a `provider` field. |
| `assign_device_resources(df, config, seed)` | Assigns capacities, unit prices, global groups, and device classes. |
| `save_results_to_csv(result, scenario_id, results_dir, ...)` | Persists optimisation outcomes and filter metadata to CSV. |

### 6.2 `pdsa.generators`

| Function | Description |
|:---|:---|
| `topology(lat, long, rad, devices_df, ...)` | Creates a topology constrained by centre, radius, providers, and device count. Writes `devices.csv`, `metadata.json`, and `map.html`. |
| `pricing_from_topology(...)` | Converts a generated topology into a pricing YAML instance (`pricing.yml`). |
| `compatible_provider_groups_from_offer(offer)` | Computes compatible provider groups from exclusion constraints. |
| `problem_instance(pricing, request, ...)` | Generates a request-constrained pricing instance and solver filter. |
| `request(demand, topology_request, users_demand, ...)` | Builds normalised request payloads for problem-instance generation. |
| `client_demand.calculate_resources(...)` | Estimates resource demand from user volume and application behaviour profiles. |

### 6.3 `pdsa.utils`

| Function | Description |
|:---|:---|
| `yaml_to_pricing_proto(yaml_path, message_type)` | Parses pricing YAML into protobuf objects. |
| `pricing_proto_to_yaml(pricing_obj, yaml_path)` | Serialises protobuf pricing instances into YAML. |
| `find_identical_addons(pricing_obj)` | Detects structurally identical add-ons. |
| `haversine(lat1, lon1, lat2, lon2)` | Great-circle distance between two geographic points. |
| `distance_3d(p1, p2)` | Euclidean distance in 3D space. |
| `point_in_polygon(point, polygon)` | Point-in-polygon test for geographic containment. |
| `distance_to_farthest_edge(point, polygon)` | Maximum distance from a point to any polygon edge. |

### 6.4 `pdsa.optimize`

```python
pdsa.optimize(
    prime_instance_url: str,
    pricing_instance_path: str,
    request: dict,
    poll_interval_seconds: float = 0.1,
    timeout_seconds: float | None = 600.0,
    session: requests.Session | None = None,
) -> dict
```

Submits a multipart optimisation job to `POST {url}/pricing/analysis`, polls
`GET {url}/pricing/analysis/{jobId}` until terminal status, and returns the final
payload (`COMPLETED` or `FAILED`).

### 6.5 `pdsa.algorithms`

The `algorithms` namespace contains the sixteen baseline implementations adapted
to the benchmark objective. Each baseline enforces six of the twelve hard
constraint types that PROMISE enforces; solutions may therefore violate provider
exclusions, feature requirements, and other constraints that PROMISE satisfies.

| Module | Function | Variants |
|:---|:---|:---|
| `benchmark.py` | `run_raom4cc_benchmark(...)` | `one_layer_mist`, `one_layer_edge`, `one_layer_cloud`, `round_robin`, `delay_heuristics`, `delay_energy_heuristics`, `best_fit`, `best_fit_delay`, `best_fit_delay_energy` |
| `edgewisecr.py` | `run_edgewisecr_benchmark(...)` | `prolog`, `prolog_cr`, `prolog_num`, `edgewise`, `edgewise_cr`, `edgewise_num` |
| `msgdp.py` | `run_msgdp_benchmark(...)` | MS-GD-P (priority-based genetic algorithm) |

Typical usage:

```python
import pandas as pd
import pricing_driven_resource_allocation as pdsa

devices = pd.read_csv("synthetic-dataset/synthetic-topologies/<uuid>/devices.csv", index_col=0)
rows = pdsa.algorithms.run_raom4cc_benchmark(
    scenario_id="small_devices_cctv_5_0",
    topology_devices=devices,
    request=request_dict,
    app="cctv",
)
```

## 7. Testing

Unit tests are provided for the RAOM4CC and EdgeWiseCR algorithm modules:

```bash
PYTHONPATH=. python -m pytest tests/test_raom4cc_algorithms.py tests/test_edgewisecr_algorithms.py -v
```

The MS-GD-P module includes an execution test (not a pytest test) that can be run
directly:

```bash
PYTHONPATH=. python -m tests.run_msgdp_algorithms
```

## 8. Documentation

In addition to this README, the repository includes detailed documentation in the
`docs/` directory:

| Document | Description |
|:---|:---|
| `results-discussion.md` | Per-technique results discussion with summary metrics tables for all 17 techniques, feasibility analysis, execution-time analysis, node-selection analysis, cost analysis, and synthesis by application type. |
| `results-discussion-grouped.md` | Per-group results discussion with summary metrics tables for 6 technique groups. Presents the same analysis at group granularity. |
| `raom4cc-benchmark-adaptations.md` | Notes on adapting RAOM4CC heuristics to the benchmark objective. |
| `raom4cc-benchmark-implementation.md` | Detailed implementation notes for the RAOM4CC adapter. |
| `edgewisecr-benchmark-adaptations.md` | Notes on adapting EdgeWiseCR engines to the benchmark. |

## 9. Data and Outputs

### Input datasets

- `eua-dataset/edge-servers/site.csv` — edge-node locations (Optus, Telstra, Vodafone)
- `eua-dataset/users/users-aus.csv` — user geolocation data
- `config/experiment_configuration.yml` — scenario definitions (3 scales × 4 applications × 2 variation axes)

### Generated artefacts

- `synthetic-dataset/synthetic-topologies/<uuid>/devices.csv` — per-topology device catalogue
- `synthetic-dataset/synthetic-topologies/<uuid>/pricing.yml` — pricing model (symbolic expressions)
- `synthetic-dataset/synthetic-topologies/<uuid>/problem_instance_pricing.yml` — resolved pricing instance (numeric prices)

### Result files

- `results/results.csv` — PROMISE optimisation outcomes (9 600 rows)
- `results/raom4cc_benchmark_results.csv` — RAOM4CC baseline results (86 400 rows)
- `results/edgewisecr_results.csv` — EdgeWiseCR baseline results (57 600 rows)
- `results/msgdp_benchmark_results.csv` — MS-GD-P baseline results (9 600 rows)
- `results/figures/*.png` — 32 publication-ready plots

## 10. License and Disclaimer

### License

This project is licensed under the MIT License. See [LICENSE](./LICENSE) for details.

### Disclaimer

This tool is part of ongoing research in pricing-driven development and operation.
It is in an early stage and is not intended for production use. The authors do not
accept responsibility for any issues or damages that may arise from its use in
real-world environments.
