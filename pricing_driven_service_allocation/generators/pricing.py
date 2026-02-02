"""
Pricing Generator Module

This module provides functions for generating pricing YAML files from topologies.
"""

import os
import yaml
import json
from datetime import date
import pandas as pd
from typing import Optional, List


def pricing_from_topology(
    topology_id: str,
    topologies_result_dir: str,
    compatible_provider_groups: Optional[List[List[str]]] = None
) -> str:
    """
    Generate a Pricing2Yaml representation of a topology and save it to a YAML file.

    Parameters
    -----------
    topology_id : str
        UUID of the topology to generate pricing for.
    topologies_result_dir : str
        Directory where topology results are stored.
    compatible_provider_groups : List[List[str]], optional
        List of provider groups that can be used together. If None, devices are
        only compatible within their own provider. Example: [["OPTUS", "TELSTRA"], ["VODAFONE"]]
        means OPTUS and TELSTRA devices can be used together, but not with VODAFONE devices.

    Returns
    --------
    str
        Path to the generated YAML file.
    """

    topology_dir = os.path.join(topologies_result_dir, topology_id)

    if not os.path.exists(topology_dir):
        raise FileNotFoundError(f"Topology directory not found: {topology_dir}")

    devices_csv_path = os.path.join(topology_dir, "devices.csv")
    devices_df = pd.read_csv(devices_csv_path, index_col=0)

    metadata_path = os.path.join(topology_dir, "metadata.json")
    with open(metadata_path, 'r') as f:
        metadata = json.load(f)

    provider_compatibility = {}
    if compatible_provider_groups is None:
        for provider in metadata['providers_in_topology']:
            provider_compatibility[provider] = [provider]
    else:
        for group in compatible_provider_groups:
            for provider in group:
                provider_compatibility[provider] = group

    addon_ids = {
        idx: f"{row['provider']}_{idx}" for idx, row in devices_df.iterrows()
    }

    device_types = sorted(devices_df['device_type'].dropna().unique().tolist())
    features = {
        device_type: {
            'type': 'DOMAIN',
            'valueType': 'BOOLEAN',
            'defaultValue': False
        }
        for device_type in device_types
    }

    pricing = {
        'saasName': topology_id,
        'syntaxVersion': '3.0',
        'version': '1.0.0',
        'createdAt': date.today().isoformat(),
        'features': features,
        'usageLimits': {
            'available_ram': {
                'unit': 'GB',
                'type': 'NON_RENEWABLE',
                'defaultValue': 0,
                'valueType': 'NUMERIC'
            },
            'available_storage': {
                'unit': 'GB',
                'type': 'NON_RENEWABLE',
                'defaultValue': 0,
                'valueType': 'NUMERIC'
            },
            'available_vcpu': {
                'unit': 'vCPU',
                'type': 'NON_RENEWABLE',
                'defaultValue': 0,
                'valueType': 'NUMERIC'
            },
            'available_gpu': {
                'unit': 'GPU',
                'type': 'NON_RENEWABLE',
                'defaultValue': 0,
                'valueType': 'NUMERIC'
            },
            'available_tpu': {
                'unit': 'TPU',
                'type': 'NON_RENEWABLE',
                'defaultValue': 0,
                'valueType': 'NUMERIC'
            },
            'distance': {
                'unit': 'meters',
                'type': 'NON_RENEWABLE',
                'defaultValue': 0,
                'valueType': 'NUMERIC'
            }
        },
        'addOns': {}
    }

    for idx, row in devices_df.iterrows():
        provider = row['provider']
        provider_device_id = addon_ids[idx]

        compatible_providers = provider_compatibility.get(provider, [provider])

        compatible_addon_ids = []
        for other_idx, other_row in devices_df.iterrows():
            other_provider = other_row['provider']
            if other_provider in compatible_providers and other_idx != idx:
                compatible_addon_ids.append(addon_ids[other_idx])

        all_addon_ids = set(addon_ids.values())
        excluded_device_ids = list(all_addon_ids - set(compatible_addon_ids) - {provider_device_id})

        addon = {
            'price': f"{row['unit_price_available_RAM']} * #available_ram + {row['unit_price_available_Storage']} * #available_storage + {row['unit_price_available_vCPU']} * #available_vcpu + {row['unit_price_available_GPU']} * #available_gpu + {row['unit_price_available_TPU']} * #available_tpu",
            'features': {
                row['device_type']: {
                    'value': True
                }
            },
            'usageLimitsExtensions': {
                'available_ram': {
                  'value': int(row['available_RAM'])
                },
                'available_storage': {
                  'value': int(row['available_Storage'])
                },
                'available_vcpu': {
                  'value': int(row['available_vCPU'])
                },
                'available_gpu': {
                  'value': int(row['available_GPU'])
                },
                'available_tpu': {
                  'value': int(row['available_TPU'])
                },
                'distance': {
                  'value': 0
                }
            },
            'excludes': excluded_device_ids if excluded_device_ids else []
        }

        addon_id = provider_device_id
        pricing['addOns'][addon_id] = addon

    yaml_path = os.path.join(topology_dir, "pricing.yml")
    with open(yaml_path, 'w', encoding='utf-8') as f:
        yaml.dump(
            pricing,
            f,
            default_flow_style=False,
            allow_unicode=True,
            sort_keys=False
        )

    print(f"Pricing YAML generated successfully!")
    print(f"  - Topology ID: {topology_id}")
    print(f"  - Devices: {len(devices_df)}")
    print(f"  - Providers: {metadata['providers_in_topology']}")
    print(f"  - File saved: {yaml_path}")

    return yaml_path
