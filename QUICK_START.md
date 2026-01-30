# Quick Start Guide

## Package Installation

### Option 1: Development Mode Installation (Recommended)

This option allows you to edit the package code and see changes immediately without reinstalling.

```bash
cd /path/to/services-allocation
pip install -e .
```

### Option 2: Regular Installation

```bash
cd /path/to/services-allocation
pip install .
```

### Verify Installation

```bash
python -c "import pricing_driven_service_allocation as pdsa; print(pdsa.__version__)"
# Should display: 1.0.0
```

## Quick Usage

### 1. From the Notebook

```bash
jupyter notebook synthetic_topologies_generator.ipynb
```

The notebook is now simplified and uses the package. Just execute the cells in order.

### 2. From a Python Script

```python
#!/usr/bin/env python3
import pricing_driven_service_allocation as pdsa

# Load data
devices_df = pdsa.load_devices_dataframe("eua-dataset/edge-servers/site.csv")

# Filter by providers
vendors = ["Telstra", "Optus", "Vodafone"]
devices_df = pdsa.filter_devices_by_vendors(devices_df, vendors)

# Assign resources (with minimal configuration)
config = {
    'attributes': {
        'available_RAM': {'min': 1, 'max': 128, 'default_price': 0.5},
        'available_Storage': {'min': 10, 'max': 2000, 'default_price': 0.2},
        'available_vCPU': {'min': 1, 'max': 64, 'default_price': 15}
    }
}
devices_df = pdsa.assign_device_resources(devices_df, config)

# Generate topology
topology_df, topology_id = pdsa.generate_topology(
    lat=-37.8136,
    long=144.9631,
    rad=5000,
    devices_df=devices_df,
    topologies_result_dir="synthetic-dataset/synthetic-topologies",
    number_of_devices=50
)

print(f"Topology generated: {topology_id}")
```

### 3. Run the Complete Example Script

```bash
python example_usage.py
```

This script demonstrates the complete workflow from data loading to problem instance generation.

## Explore the Documentation

### View Function Help

```python
import pricing_driven_service_allocation as pdsa

# View complete documentation
help(pdsa.generate_topology)

# View just the signature
print(pdsa.generate_topology.__doc__)
```

### List All Available Functions

```python
import pricing_driven_service_allocation as pdsa

print(dir(pdsa))
```

### Read the Package README

```bash
cat pricing_driven_service_allocation/README.md
```

## Expected Directory Structure

```
services-allocation/
├── eua-dataset/                    # Input data (must exist)
│   └── edge-servers/
│       └── site.csv
├── synthetic-dataset/              # Will be created automatically
│   ├── data/
│   └── synthetic-topologies/
├── problem-instances/              # Will be created automatically
└── iPricing/                       # Protobuf models (must exist)
    └── model/
        └── iPricing_pb2.py
```

## Common Troubleshooting

### Error: "ModuleNotFoundError: No module named 'pricing_driven_service_allocation'"

**Solution:**
```bash
pip install -e .
```

### Error: "No module named 'iPricing'"

**Solution:**
```bash
protoc --python_out=./iPricing/model ./iPricing/iPricing.proto
```

### Error: "ModuleNotFoundError: No module named 'shapely'"

**Solution:**
```bash
pip install shapely
# or
pip install -r requirements.txt
```

### Notebook can't find the package

**Solution:**
1. Make sure you're in the correct environment
2. Reinstall the package:
   ```bash
   pip install -e .
   ```
3. Restart the notebook kernel: Kernel → Restart

## Useful Commands

### Reinstall the Package

```bash
pip install -e . --force-reinstall
```

### View Package Information

```bash
pip show pricing-driven-service-allocation
```

### Uninstall the Package

```bash
pip uninstall pricing-driven-service-allocation
```

### Update Dependencies

```bash
pip install -r requirements.txt --upgrade
```

## Next Steps

1. ✅ Install the package: `pip install -e .`
2. ✅ Run the example: `python example_usage.py`
3. ✅ Explore the notebook: `jupyter notebook synthetic_topologies_generator.ipynb`
4. ✅ Read the documentation: `cat pricing_driven_service_allocation/README.md`
5. ✅ Adapt to your needs

## Additional Resources

- **Main README:** [README.md](README.md)
- **Package Documentation:** [pricing_driven_service_allocation/README.md](pricing_driven_service_allocation/README.md)
- **Migration Summary:** [MIGRATION_SUMMARY.md](MIGRATION_SUMMARY.md)
- **Example Script:** [example_usage.py](example_usage.py)

---

Have questions? Check the documentation or open an issue in the repository.
