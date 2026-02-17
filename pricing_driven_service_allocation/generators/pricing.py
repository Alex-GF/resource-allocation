"""
Pricing Generator Module

This module provides functions for generating pricing YAML files from topologies.
"""

import os
import yaml
import json
from datetime import date
import pandas as pd
from typing import Optional, List, Dict, Any


def pricing_from_topology(
    topology_id: str,
    topologies_result_dir: str,
    resources_to_consider: List[str],
    compatible_provider_groups: Optional[List[List[str]]] = None,
    options: Optional[Dict[str, Any]] = None
) -> str:
    """
    Generate a Pricing2Yaml representation of a topology and save it to a YAML file.
    """

    if options is None:
        options = {}

    topology_dir = os.path.join(topologies_result_dir, topology_id)
    if not os.path.exists(topology_dir):
        raise FileNotFoundError(f"Topology directory not found: {topology_dir}")

    devices_csv_path = os.path.join(topology_dir, "devices.csv")
    devices_df = pd.read_csv(devices_csv_path, index_col=0)

    metadata_path = os.path.join(topology_dir, "metadata.json")
    with open(metadata_path, "r") as f:
        metadata = json.load(f)

    # -----------------------------
    # Provider compatibility
    # -----------------------------
    provider_compatibility: Dict[str, List[str]] = {}
    if compatible_provider_groups is None:
        for provider in metadata["providers_in_topology"]:
            provider_compatibility[provider] = [provider]
    else:
        for group in compatible_provider_groups:
            for provider in group:
                provider_compatibility[provider] = group

    # -----------------------------
    # Add-on identifiers
    # -----------------------------
    addon_ids = {idx: f"{row['provider']}_{idx}" for idx, row in devices_df.iterrows()}
    all_addon_ids = set(addon_ids.values())

    # -----------------------------
    # Features from device types
    # -----------------------------
    device_types = sorted(devices_df["device_type"].dropna().unique().tolist())
    features = {
        device_type: {"type": "DOMAIN", "valueType": "BOOLEAN", "defaultValue": False}
        for device_type in device_types
    }

    # -----------------------------
    # Usage limits metadata
    # -----------------------------
    default_usage_limit_metadata = {
        "available_ram_gb": {"unit": "GB", "type": "NON_RENEWABLE", "valueType": "NUMERIC"},
        "available_storage_gb": {"unit": "GB", "type": "NON_RENEWABLE", "valueType": "NUMERIC"},
        "available_cpu_cores": {"unit": "cores", "type": "NON_RENEWABLE", "valueType": "NUMERIC"},
        "available_gpu_units": {"unit": "GPU_UNITS", "type": "NON_RENEWABLE", "valueType": "NUMERIC"},
        "available_tpu_units": {"unit": "TPU_UNITS", "type": "NON_RENEWABLE", "valueType": "NUMERIC"},
        "available_network_in_mbps": {"unit": "Mbps", "type": "NON_RENEWABLE", "valueType": "NUMERIC"},
        "available_network_out_mbps": {"unit": "Mbps", "type": "NON_RENEWABLE", "valueType": "NUMERIC"},
        "distance": {"unit": "meters", "type": "NON_RENEWABLE", "valueType": "NUMERIC"},
    }

    usage_limit_overrides: Dict[str, Dict[str, Any]] = options.get("usage_limit_metadata", {})

    def build_usage_limit_block(resource_name: str) -> Dict[str, Any]:
        meta = dict(default_usage_limit_metadata.get(resource_name, {}))
        meta.update(usage_limit_overrides.get(resource_name, {}))
        meta.setdefault("unit", "unit")
        meta.setdefault("type", "NON_RENEWABLE")
        meta.setdefault("valueType", "NUMERIC")
        meta["defaultValue"] = 0
        return meta

    distance_limit_name = options.get("distance_limit_name", "distance")

    effective_resources = list(resources_to_consider)
    if distance_limit_name and distance_limit_name not in effective_resources:
        effective_resources.append(distance_limit_name)

    usage_limits_block = {res: build_usage_limit_block(res) for res in effective_resources}

    # -----------------------------
    # Column mappings
    # -----------------------------
    column_map: Dict[str, str] = options.get("column_map", {})
    price_column_map: Dict[str, str] = options.get("price_column_map", {})
    unit_price_prefix: str = options.get("unit_price_prefix", "unit_price_")

    def capacity_col(resource_name: str) -> str:
        return column_map.get(resource_name, resource_name)

    def unit_price_col(resource_name: str) -> str:
        if resource_name in price_column_map:
            return price_column_map[resource_name]
        return f"{unit_price_prefix}{capacity_col(resource_name)}"

    resources_requiring_columns = list(resources_to_consider)

    missing_caps = [res for res in resources_requiring_columns if capacity_col(res) not in devices_df.columns]
    missing_prices = [res for res in resources_requiring_columns if unit_price_col(res) not in devices_df.columns]

    if missing_caps:
        raise KeyError(
            "Missing capacity columns for resources_to_consider: "
            + ", ".join(f"{res}->{capacity_col(res)}" for res in missing_caps)
        )

    if missing_prices:
        raise KeyError(
            "Missing unit price columns for resources_to_consider: "
            + ", ".join(f"{res}->{unit_price_col(res)}" for res in missing_prices)
        )

    # -----------------------------
    # Pricing root
    # -----------------------------
    pricing: Dict[str, Any] = {
        "saasName": topology_id,
        "syntaxVersion": "3.0",
        "version": "1.0.0",
        "createdAt": date.today().isoformat(),
        "features": features,
        "usageLimits": usage_limits_block,
        "addOns": {},
    }

    # -----------------------------
    # FIX: Add-on deduplication by content signature
    # -----------------------------
    seen_signatures: set[str] = set()

    def addon_signature(addon: Dict[str, Any]) -> str:
        # Canonical JSON string: stable across dict ordering
        # The signature ignores the add-on id, by design.
        return json.dumps(addon, sort_keys=True, separators=(",", ":"), ensure_ascii=True)

    # -----------------------------
    # Add-ons (one per device)
    # -----------------------------
    for idx, row in devices_df.iterrows():
        provider = row["provider"]
        addon_id = addon_ids[idx]

        compatible_providers = provider_compatibility.get(provider, [provider])

        compatible_addons = [
            addon_ids[o_idx]
            for o_idx, o_row in devices_df.iterrows()
            if o_idx != idx and o_row["provider"] in compatible_providers
        ]

        excluded_device_ids = list(all_addon_ids - set(compatible_addons) - {addon_id})

        price_terms = []
        for res in resources_to_consider:
            price_val = float(row[unit_price_col(res)])
            price_terms.append(f"{price_val} * #{res}")
        price_expr = " + ".join(price_terms) if price_terms else "0"

        usage_ext: Dict[str, Dict[str, Any]] = {}
        for res in resources_to_consider:
            val = row[capacity_col(res)]
            if pd.isna(val):
                val = 0
            val = float(val)
            if abs(val - round(val)) < 1e-9:
                val = int(round(val))
            usage_ext[res] = {"value": val}

        addon_obj = {
            "price": price_expr,
            "features": {row["device_type"]: {"value": True}},
            "usageLimitsExtensions": usage_ext,
            "excludes": excluded_device_ids if excluded_device_ids else [],
        }

        sig = addon_signature(addon_obj)
        if sig in seen_signatures:
            # Duplicate: skip it
            continue

        seen_signatures.add(sig)
        pricing["addOns"][addon_id] = addon_obj

    # -----------------------------
    # Persist YAML
    # -----------------------------
    yaml_path = os.path.join(topology_dir, "pricing.yml")
    with open(yaml_path, "w", encoding="utf-8") as f:
        yaml.dump(
            pricing,
            f,
            default_flow_style=False,
            allow_unicode=True,
            sort_keys=False
        )

    if options.get("logs", True):
        print("Pricing YAML generated successfully!")
        print(f"  - Topology ID: {topology_id}")
        print(f"  - Devices: {len(devices_df)}")
        print(f"  - Add-ons (after dedup): {len(pricing['addOns'])}")
        print(f"  - Providers: {metadata['providers_in_topology']}")
        print(f"  - Resources considered: {effective_resources}")
        print(f"  - File saved: {yaml_path}")

    return yaml_path

def compatible_provider_groups_from_offer(topology_offer: dict) -> List[List[str]]:
    """
    Extract compatible provider groups from a topology offer.

    Parameters
    ----------
    topology_offer : dict
        The topology offer containing provider compatibility information.
        Expected format:
        {
            'providers': {
                'OPTUS': {
                    'excludes': ['TELSTRA'],
                    'includes': ['VODAFONE']
                },
                'TELSTRA': {
                    'includes': ['VODAFONE']
                },
                ...
            }
        }

    Returns
    -------
    List[List[str]]
        A list of compatible provider groups. Each sublist represents a group of
        providers that can work together.
        Example: [['OPTUS', 'VODAFONE'], ['TELSTRA', 'VODAFONE']]
    """
    providers_config = topology_offer.get('providers', {})
    
    # Build compatibility groups for each provider
    provider_groups = []
    
    for provider_name, config in providers_config.items():
        # Start with the provider itself
        compatible_group = {provider_name.upper()}
        
        # Add providers from 'includes' list
        includes = config.get('includes', [])
        for included_provider in includes:
            compatible_group.add(included_provider.upper())
        
        # Remove providers from 'excludes' list
        excludes = config.get('excludes', [])
        for excluded_provider in excludes:
            compatible_group.discard(excluded_provider.upper())
        
        # Add this group to the list
        provider_groups.append(sorted(list(compatible_group)))
    
    # Remove duplicates by converting to tuples, using set, then back to lists
    unique_groups = list(set(tuple(sorted(group)) for group in provider_groups))
    
    # Convert back to list of lists
    result = [list(group) for group in unique_groups]
    
    return result
    