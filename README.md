# Services Allocation

Research project for pricing-driven service allocation and resource optimization on geographically distributed devices.

## Project Structure

```
services-allocation/
├── pricing_driven_service_allocation/  # Main Python package
│   ├── __init__.py
│   ├── data_loading.py
│   ├── resource_assignment.py
│   ├── utils.py
│   ├── topology_generator.py
│   ├── pricing_generator.py
│   ├── problem_instance.py
│   └── README.md
├── synthetic_topologies_generator.ipynb  # Simplified notebook
├── example_usage.py                      # Example script
├── setup.py                              # Package configuration
├── requirements.txt                      # Project dependencies
├── eua-dataset/                          # Input data
├── synthetic-dataset/                    # Generated data
├── problem-instances/                    # Problem instances
└── iPricing/                             # Protocol Buffer models
```

## Installation

### 1. Clone the repository

```bash
git clone <repository-url>
cd services-allocation
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Install the local package

```bash
pip install -e .
```

### 4. Generate Protocol Buffer models (if necessary)

```bash
protoc --python_out=./iPricing/model ./iPricing/iPricing.proto
```

## Usage

### Option 1: Use the Notebook

The `synthetic_topologies_generator.ipynb` notebook is now simplified and uses the `pricing_driven_service_allocation` package for all main operations.

```bash
jupyter notebook synthetic_topologies_generator.ipynb
```

### Option 2: Use the Example Script

```bash
python example_usage.py
```

### Option 3: Import the Package in Your Scripts

```python
import pricing_driven_service_allocation as pdsa

# Load data
devices_df = pdsa.load_devices_dataframe("path/to/devices.csv")

# Filter by providers
devices_df = pdsa.filter_devices_by_vendors(devices_df, ["Telstra", "Optus"])

# Assign resources
config = {...}  # See package documentation
devices_df = pdsa.assign_device_resources(devices_df, config)

# Generate topology
topology_df, topology_id = pdsa.generate_topology(
    lat=-37.8136,
    long=144.9631,
    rad=5000,
    devices_df=devices_df,
    topologies_result_dir="synthetic-dataset/synthetic-topologies",
    number_of_providers=3
)

# Generate pricing
pricing_path = pdsa.generate_pricing_from_topology(
    topology_id=topology_id,
    topologies_result_dir="synthetic-dataset/synthetic-topologies"
)

# Generate problem instance
from iPricing.model.iPricing_pb2 import Pricing
pricing_obj = pdsa.yaml_to_proto(pricing_path, Pricing)

request = {
    'currency': 'USD',
    'providers_to_consider': ['telstra'],
    'budget': 1000,
    'resources': {
        'available_ram': 5,
        'available_storage': 500,
        'available_vcpu': 4
    }
}

problem_instance, filter_criteria = pdsa.generate_problem_instance(
    instance_pricing=pricing_obj,
    request=request,
    topologies_result_dir="synthetic-dataset/synthetic-topologies"
)
```

## Package Documentation

For more details about the `pricing_driven_service_allocation` package, see:

```bash
cat pricing_driven_service_allocation/README.md
```

Or visit the [package documentation](pricing_driven_service_allocation/README.md).

## Main Features

1. **Data Loading and Preprocessing**: Functions to load device datasets from CSV
2. **Resource Assignment**: Flexible configuration to assign capacities and prices to devices
3. **Topology Generation**: Create geographic topologies with advanced filters
4. **Pricing Generation**: Convert topologies to pricing YAML files
5. **Problem Instances**: Generate problem instances by combining pricing with user requests
6. **Geospatial Utilities**: Distance calculations, polygons, and 3D operations

## Modularization Benefits

- ✅ **Maintainability**: Code organized in logical modules
- ✅ **Reusability**: Functions available as a Python package
- ✅ **Testability**: Easy to test each module independently
- ✅ **Documentation**: Each function is well documented
- ✅ **Scalability**: Easy to add new functionalities
- ✅ **Simplicity**: Cleaner notebook focused on workflow

## Contributing

To contribute to the project:

1. Create a branch for your feature
2. Implement changes in the `pricing_driven_service_allocation` package
3. Update tests (if applicable)
4. Update documentation
5. Submit a pull request

## License

See LICENSE file for more details.