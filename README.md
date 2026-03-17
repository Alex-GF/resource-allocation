# Pricing-Driven Resource Allocation in the Cloud Continuum – Laboratory Package

This repository contains the implementation used to study pricing-driven resource allocation in the cloud continuum. The workflow generates topology-specific pricing models, creates constrained problem instances, and delegates optimization to PRIME through its REST API.

The project is intended for research-grade experimentation and reproducibility.

## Table of Contents

1. [Project Structure](#project-structure)
2. [How to Reproduce the Experiment](#how-to-reproduce-the-experiment)
3. [API of pricing_driven_resource_allocation](#api-of-pricing_driven_resource_allocation)
4. [Data and Outputs](#data-and-outputs)
5. [License](#license)

## Project Structure

The repository is organized as follows (main elements only):

```text
services-allocation/
├── config/
│   └── experiment_configuration.yml      # Scenario definitions (small/medium/large)
├── docker-compose.yml                    # PRIME analysis API service (port 3000)
├── evaluation.ipynb                      # End-to-end experimental pipeline
├── eua-dataset/
│   ├── edge-servers/                     # Input edge-node datasets
│   └── users/                            # Input user-location datasets
├── iPricing/
│   ├── iPricing.proto                    # Pricing model schema
│   └── model/                            # Generated Python protobuf module
├── pricing_driven_resource_allocation/   # Core Python package
│   ├── __init__.py
│   ├── optimize.py                       # PRIME API client and polling loop
│   ├── dataset/
│   │   ├── load.py                       # Dataset loading utilities
│   │   ├── transform.py                  # Filtering and resource assignment
│   │   └── save_results.py               # Results persistence (CSV)
│   ├── generators/
│   │   ├── topology.py                   # Topology synthesis per scenario
│   │   ├── pricing.py                    # Pricing YAML generation
│   │   ├── problem_instance.py           # Request-constrained instance construction
│   │   ├── client_demand.py              # Demand modeling by application class
│   │   └── request.py                    # Request payload builder
│   └── utils/
│       ├── geometrical_utils.py          # Spatial computations
│       └── yaml_utils.py                 # YAML <-> protobuf conversion helpers
├── results/
│   ├── results.csv                       # Aggregated optimization outcomes
│   └── figures/                          # Publication-ready plots
├── synthetic-dataset/
│   ├── data/
│   └── synthetic-topologies/             # 9600 generated topologies and instances
├── requirements.txt
├── setup.py
└── README.md
```

## How to Reproduce the Experiment

> [!WARNING]  
> The execution of this experiment can be computationally intensive and may require several hours, particularly when running the large-scale scenario. Before starting the procedure, ensure that adequate computational resources and sufficient uninterrupted execution time are available.
>
> For reference, the experiment was conducted on a workstation equipped with an Apple Silicon M4 Pro processor and 24 gigabytes of main memory, where the complete execution required approximately **ten hours**.

### 1. Prerequisites

- Python 3.10+ recommended
- Docker and Docker Compose
- Protocol Buffers compiler (`protoc`)
- Jupyter (to execute `evaluation.ipynb`)

### 2. Clone and install

```bash
git clone <repository-url>
cd services-allocation
python -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
pip install -e .
```

### 3. Confirm port 3000 is available

Before launching PRIME, verify that no process is currently bound to TCP port 3000:

```bash
lsof -i :3000
```

If the command returns any process, release the port before continuing.

### 4. Start PRIME from the project root

From the repository root, launch the PRIME service exactly as follows:

```bash
docker-compose up -d
```

Then verify health:

```bash
curl http://localhost:3000/health
```

The notebook uses `PRIME_INSTANCE_URL = "http://localhost:3000/api/v1/"`, therefore PRIME must be reachable on port 3000. If you run PRIME on any other port, remember to update the URL in the first cell of `evaluation.ipynb` accordingly.

### 5. Execute the experiment pipeline

Run the notebook and execute all cells in order:

```bash
jupyter notebook evaluation.ipynb
```

Pipeline stages implemented in the notebook:

1. Initialize constants, paths, offer configuration, and resources.
2. Load and validate `config/experiment_configuration.yml`.
3. Load and preprocess the EUA edge dataset.
4. Generate topologies for each scenario and repetition.
5. Build pricing files and scenario-specific problem instances.
6. Invoke PRIME optimization through `pdsa.optimize(...)`.
7. Persist execution metrics in `results/results.csv` and generate figures in `results/figures/`.

### 6. Stop services after completion

```bash
docker-compose down
```

## API of pricing_driven_resource_allocation

The package exposes four public namespaces at the top level:

- `pdsa.dataset`
- `pdsa.generators`
- `pdsa.utils`
- `pdsa.optimize`

### Top-level API

```python
import pricing_driven_resource_allocation as pdsa

pdsa.optimize(...)
pdsa.dataset.*
pdsa.generators.*
pdsa.utils.*
```

### `pdsa.dataset`

- `load_devices_dataframe(path: str) -> pandas.DataFrame`
    Loads the raw edge device CSV and standardizes column names.
- `load_client_locations_dataframe(path: str) -> pandas.DataFrame`
    Loads and normalizes client geolocation data.
- `filter_devices_by_vendors(devices_df: pandas.DataFrame, vendors_to_consider: list) -> pandas.DataFrame`
    Filters devices by provider tokens in device names and adds a normalized `provider` field.
- `assign_device_resources(df: pandas.DataFrame, config: dict | None = None, seed: int | None = None) -> pandas.DataFrame`
    Assigns capacities, prices, global groups, and device classes according to configurable stochastic rules.
- `save_results_to_csv(result_obj: dict, scenario_id: str, RESULTS_DIR: str, filename: str = "results.csv", include_filter: bool = True) -> None`
    Stores optimization outcomes and filter metadata in CSV format.

### `pdsa.generators`

- `topology(...) -> tuple[pandas.DataFrame, str]`
    Creates a topology constrained by center, radius, providers, and device count; writes `devices.csv`, `metadata.json`, and `map.html`.

    Core signature:

    ```python
    pdsa.generators.topology(
            lat: float,
            long: float,
            rad: float,
            devices_df: pandas.DataFrame,
            topologies_result_dir: str,
            resources_to_consider: list[str],
            number_of_providers: int | None = None,
            allowed_groups: list[int] | None = None,
            number_of_devices: int | None = None,
            center_elevation: float = 0.0,
            options: dict | None = None,
    )
    ```

- `pricing_from_topology(...) -> str`
    Converts a generated topology into a pricing YAML instance (`pricing.yml`).
- `compatible_provider_groups_from_offer(topology_offer: dict) -> list[list[str]]`
    Computes compatible provider groups from exclusion constraints.
- `problem_instance(instance_pricing, request: dict, topologies_result_dir: str, unlimited_value: int = 100000000, options: dict = ...) -> tuple`
    Generates a request-constrained pricing instance and a solver filter.
- `request(topology_demand: dict, topology_request: dict, users_demand: dict, resources_to_consider: list[str], currency: str = "USD", resource_mapping: dict | None = None) -> dict`
    Builds normalized request payloads for problem-instance generation.
- `client_demand.calculate_resources(...) -> dict`
    Estimates resource demand from user volume and application behavior profiles.

### `pdsa.utils`

- `yaml_to_pricing_proto(yaml_path: str, message_type)`
    Parses pricing YAML into protobuf objects.
- `pricing_proto_to_yaml(pricing_obj, yaml_path: str, options: dict | None = None) -> None`
    Serializes protobuf pricing instances into YAML.
- `find_identical_addons(pricing_obj) -> list[tuple[str, str]]`
    Detects structurally identical add-ons.
- `haversine(...) -> float`
- `distance_3d(...) -> float`
- `point_in_polygon(...) -> bool`
- `distance_to_farthest_edge(...) -> float`

### `pdsa.optimize`

- `optimize(prime_instance_url: str, pricing_instance_path: str, request: dict, poll_interval_seconds: float = 0.1, timeout_seconds: float | None = 600.0, session: requests.Session | None = None) -> dict`

Behavior:

1. Submits a multipart optimization job to `POST {prime_instance_url}/pricing/analysis`.
2. Polls `GET {prime_instance_url}/pricing/analysis/{jobId}` until terminal status.
3. Returns the final payload (`COMPLETED` or `FAILED`).

## Data and Outputs

- Input datasets:
  - `eua-dataset/edge-servers/site.csv`
  - `eua-dataset/users/users-aus.csv`
- Scenario specification:
  - `config/experiment_configuration.yml`
- Generated artifacts:
  - `synthetic-dataset/synthetic-topologies/<topology_id>/devices.csv`
  - `synthetic-dataset/synthetic-topologies/<topology_id>/pricing.yml`
  - `synthetic-dataset/synthetic-topologies/<topology_id>/problem_instance_pricing.yml`
  - `results/results.csv`
  - `results/figures/*.png`

## ⚠️ Disclaimer & License

### LICENSE

This project is licensed under the MIT License. See [LICENSE](./LICENSE) for details

### DISCLAIMER

This tool is part of ongoing research by the [ISA group](https://github.com/isa-group) in pricing-driven development and operation. It is in an **early stage** and is not intended for production use. The ISA group does not accept responsibility for any issues or damages that may arise from its use in real-world environments
