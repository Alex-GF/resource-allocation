#!/usr/bin/env python3
"""
Example script demonstrating how to use the pricing_driven_service_allocation package.

This script shows a complete workflow from loading data to generating problem instances.

Note: This example demonstrates the generators subpackage with short function names.
You can use either:
  - pdsa.generators.topology()              (recommended - clean names)
  - pdsa.generate_topology()                 (backward compatible - verbose)
"""

import os
import pricing_driven_service_allocation as pdsa
from iPricing.model.iPricing_pb2 import Pricing

# Configuration
DATASET_RESULT_DIR = "synthetic-dataset/data"
TOPOLOGIES_RESULT_DIR = "synthetic-dataset/synthetic-topologies"
DEVICES_DATASET_PATH = "eua-dataset/edge-servers/site.csv"
VENDORS_TO_CONSIDER = ["Telstra", "Optus", "Vodafone", "Telecom", "Macquarie"]
UNLIMITED_VALUE = 100000000

def main():
    """Main function demonstrating the package usage."""
    
    print("=" * 80)
    print("PRICING-DRIVEN SERVICE ALLOCATION - EXAMPLE WORKFLOW")
    print("=" * 80)
    
    # Step 1: Load and preprocess device data
    print("\n[Step 1] Loading device data...")
    devices_df = pdsa.load_devices_dataframe(DEVICES_DATASET_PATH)
    print(f"  ✓ Loaded {len(devices_df)} devices")
    
    # Step 2: Filter by vendors
    print("\n[Step 2] Filtering by vendors...")
    devices_df = pdsa.filter_devices_by_vendors(devices_df, VENDORS_TO_CONSIDER)
    print(f"  ✓ Filtered to {len(devices_df)} devices")
    
    # Step 3: Assign resources
    print("\n[Step 3] Assigning resources to devices...")
    custom_config = {
        'global': {
            'group_percentages': {1: 83, 2: 15, 3: 2},
            'group_ranges': {1: (0, 12.5), 2: (12.5, 50), 3: (50, 100)}
        },
        'attributes': {
            'available_RAM': {
                'min': 1,
                'max': 128,
                'default_price': 0.5,
                'price_by_provider_group': {
                    'OPTUS': {1: 1, 2: 0.15, 3: 0.005},
                    'TELSTRA': {1: 1.3, 2: 0.12, 3: 0.003},
                }
            },
            'available_Storage': {
                'min': 1,
                'max': 100000,
                'default_price': 0.2
            },
            'available_vCPU': {
                'min': 1,
                'max': 64,
                'default_price': 15
            },
            'available_GPU': {
                'min': 0,
                'max': 8,
                'default_price': 120
            },
            'available_TPU': {
                'min': 0,
                'max': 4,
                'default_price': 200
            }
        }
    }
    
    devices_df = pdsa.assign_device_resources(devices_df, custom_config)
    print(f"  ✓ Resources assigned to all devices")
    print(f"    - Group distribution: {dict(devices_df['global_group'].value_counts().sort_index())}")
    
    # Step 4: Save processed dataset
    print("\n[Step 4] Saving processed dataset...")
    os.makedirs(DATASET_RESULT_DIR, exist_ok=True)
    devices_df.to_csv(os.path.join(DATASET_RESULT_DIR, "devices.csv"))
    print(f"  ✓ Dataset saved to {DATASET_RESULT_DIR}/devices.csv")
    
    # Step 5: Generate topology using generators subpackage
    print("\n[Step 5] Generating topology...")
    topology_devices, topology_id = pdsa.generators.topology(
        lat=-37.8136,
        long=144.9631,
        rad=5000,
        devices_df=devices_df,
        topologies_result_dir=TOPOLOGIES_RESULT_DIR,
        number_of_providers=3,
        allowed_groups=[2, 3],
        number_of_devices=50
    )
    print(f"  ✓ Topology generated with ID: {topology_id}")
    
    # Step 6: Generate pricing YAML using generators subpackage
    print("\n[Step 6] Generating pricing YAML...")
    pricing_path = pdsa.generators.pricing(
        topology_id=topology_id,
        topologies_result_dir=TOPOLOGIES_RESULT_DIR
    )
    print(f"  ✓ Pricing saved to {pricing_path}")
    
    # Step 7: Load pricing as Protocol Buffer
    print("\n[Step 7] Loading pricing as Protocol Buffer...")
    pricing_obj = pdsa.generators.yaml_to_proto(pricing_path, Pricing)
    print(f"  ✓ Pricing loaded for {pricing_obj.saasName}")
    
    # Step 8: Generate problem instance using generators subpackage
    print("\n[Step 8] Generating problem instance...")
    custom_request = {
        'currency': 'USD',
        'users_location': [
            (144.8588538568788, -37.84750988098617),
            (144.8588538568788, -37.857590074634246),
            (144.87928006127504, -37.857590074634246),
            (144.87928006127504, -37.84750988098617),
            (144.8588538568788, -37.84750988098617)
        ],
        'providers_to_consider': ['telstra'],
        'budget': 1000,
        'max_devices': 2,
        'resources': {
            'available_ram': 5,
            'available_storage': 500,
            'available_vcpu': 4,
            'available_gpu': 1,
            'available_tpu': 0,
        },
        'max_distance': 10000,
    }
    
    problem_instance_pricing, filter_criteria = pdsa.generators.problem_instance(
        instance_pricing=pricing_obj,
        request=custom_request,
        topologies_result_dir=TOPOLOGIES_RESULT_DIR,
        unlimited_value=UNLIMITED_VALUE
    )
    
    print(f"  ✓ Problem instance generated")
    print(f"    - Original add-ons: {len(pricing_obj.addOns)}")
    print(f"    - Filtered add-ons: {len(problem_instance_pricing.addOns)}")
    print(f"    - Budget constraint: {filter_criteria.get('maxPrice', 'N/A')}")
    print(f"    - Max devices: {filter_criteria.get('maxSubscriptionSize', 'N/A')}")
    
    # Step 9: Save problem instance
    print("\n[Step 9] Saving problem instance...")
    problem_instance_path = os.path.join(
        TOPOLOGIES_RESULT_DIR, 
        topology_id, 
        "problem_instance_pricing.yml"
    )
    pdsa.generators.save_pricing_proto_to_yaml(problem_instance_pricing, problem_instance_path)
    
    print("\n" + "=" * 80)
    print("WORKFLOW COMPLETED SUCCESSFULLY!")
    print("=" * 80)
    print(f"\nGenerated files:")
    print(f"  - Devices dataset: {DATASET_RESULT_DIR}/devices.csv")
    print(f"  - Topology data: {TOPOLOGIES_RESULT_DIR}/{topology_id}/")
    print(f"  - Pricing YAML: {pricing_path}")
    print(f"  - Problem instance: {problem_instance_path}")
    print()


if __name__ == "__main__":
    main()
