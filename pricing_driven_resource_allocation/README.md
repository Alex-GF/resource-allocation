# Pricing-Driven Service Allocation

Python package for device topology management, resource allocation, and pricing for service allocation problems.

## Installation

The package can be installed locally from the project directory:

```bash
pip install -e .
```

## Package Structure

```
pricing_driven_resource_allocation/
├── __init__.py              # Main package file
├── data_loading.py          # Data loading and preprocessing
├── resource_assignment.py   # Resource assignment to devices
├── utils.py                 # Utilities (distance calculations, geometry)
├── README.md                # This file
└── generators/              # Generators subpackage
    ├── __init__.py          # Generators subpackage initialization
    ├── topology_generator.py    # Topology generation
    ├── pricing_generator.py     # Pricing YAML file generation
    └── problem_instance.py      # Problem instance generation
```

## Modules

### data_loading
Functions for loading and preprocessing device datasets.

**Main functions:**
- `load_devices_dataframe(path)`: Loads a device CSV and standardizes columns
- `filter_devices_by_vendors(devices_df, vendors_to_consider)`: Filters devices by provider

### resource_assignment
Functions for assigning resources and prices to devices.

**Main functions:**
- `assign_device_resources(df, config)`: Assigns resource capacities and unit prices to each device

### utils
Utility functions for distance calculations and geometric operations.

**Main functions:**
- `haversine(lon1, lat1, lon2, lat2)`: Calculates horizontal distance between two points
- `distance_3d(lon1, lat1, lon2, lat2, elev1, elev2)`: Calculates 3D distance considering elevation
- `point_in_polygon(lat, lon, polygon_coords)`: Checks if a point is inside a polygon
- `distance_to_farthest_edge(lat, lon, polygon_coords)`: Calculates maximum distance to polygon edges

### generators (Subpackage)
Subpackage containing all generator functions organized by functionality.

#### generators.topology
Functions for generating device topologies within geographic areas.

**Main functions:**
- `topology(lat, long, rad, devices_df, topologies_result_dir, ...)`: Generates a device topology within a circular area

#### generators.pricing
Functions for generating pricing files in YAML format from topologies.

**Main functions:**
- `pricing(topology_id, topologies_result_dir, compatible_provider_groups)`: Generates a pricing YAML file from a topology
  - Also available as `pricing_from_topology()` within the module

#### generators.problem_instance
Functions for generating problem instances from pricing and user requests.

**Main functions:**
- `problem_instance(instance_pricing, request, topologies_result_dir, ...)`: Generates a problem instance from pricing and request
- `yaml_to_proto(yaml_path, message_type)`: Converts a YAML file to a Protocol Buffer message
- `resolve_price(addon_details, resources, unlimited_value)`: Evaluates a price expression
- `save_pricing_proto_to_yaml(pricing_obj, yaml_path)`: Saves a Pricing object in YAML format

## Usage Example

### Option 1: Using generators subpackage (Recommended)

```python
import pricing_driven_resource_allocation as pdsa

# 1. Load device data
devices_df = pdsa.load_devices_dataframe("path/to/devices.csv")

# 2. Filter by providers
vendors = ["Telstra", "Optus", "Vodafone"]
devices_df = pdsa.filter_devices_by_vendors(devices_df, vendors)

# 3. Assign resources
config = {
    'global': {
        'group_percentages': {1: 83, 2: 15, 3: 2},
        'group_ranges': {1: (0, 12.5), 2: (12.5, 50), 3: (50, 100)}
    },
    'attributes': {
        'available_RAM': {'min': 1, 'max': 128, 'default_price': 0.5}
    }
}
devices_df = pdsa.assign_device_resources(devices_df, config)

# 4. Generate topology using generators subpackage
topology_df, topology_id = pdsa.generators.topology(
    lat=-37.8136,
    long=144.9631,
    rad=5000,
    devices_df=devices_df,
    topologies_result_dir="synthetic-dataset/synthetic-topologies",
    number_of_providers=3,
    allowed_groups=[2, 3],
    number_of_devices=50
)

# 5. Generate pricing using generators subpackage
pricing_path = pdsa.generators.pricing(
    topology_id=topology_id,
    topologies_result_dir="synthetic-dataset/synthetic-topologies"
)

# 6. Generate problem instance using generators subpackage
pdsa.generators.problem_instance(
    instance_pricing=pricing_path,
    request="path/to/request.yaml",
    topologies_result_dir="synthetic-dataset/synthetic-topologies",
    problem_instances_result_dir="problem-instances"
)
```

### Option 2: Direct imports (Backward compatibility)

```python
import pricing_driven_resource_allocation as pdsa

# Generator functions are also available at top level with verbose names
topology_df, topology_id = pdsa.generate_topology(...)
pricing_path = pdsa.generate_pricing_from_topology(...)
```

## Requirements

- pandas
- numpy
- shapely
- pyyaml
- protobuf

## License

See LICENSE file in the project root directory.
