"""
Data Loading Module

This module provides functions for preprocessing device datasets.
"""

import numpy as np
import pandas as pd
from typing import Dict, Optional, Any

def filter_devices_by_vendors(devices_df: pd.DataFrame, vendors_to_consider: list) -> pd.DataFrame:
    """
    Filter devices by vendor names and extract provider information.
    
    Parameters
    ----------
    devices_df : pd.DataFrame
        DataFrame containing device information.
    vendors_to_consider : list
        List of vendor names to keep.
    
    Returns
    -------
    pd.DataFrame
        Filtered DataFrame with provider column added.
    """
    import re
    
    # Filter devices by vendor names
    pattern = "|".join(re.escape(v) for v in vendors_to_consider)
    mask = devices_df["name"].str.contains(pattern, case=False, na=False)
    devices_df = devices_df.loc[mask].copy()

    # Extract and standardize provider names
    devices_df["provider"] = (
        devices_df["name"]
        .str.extract(f"({pattern})", flags=re.IGNORECASE)[0]
        .str.upper()
    )

    # Drop the original name column
    devices_df.drop(columns=["name"], inplace=True)

    return devices_df

def assign_device_resources(
    df: pd.DataFrame,
    config: Optional[Dict[str, Any]] = None,
    seed: Optional[int] = None
) -> pd.DataFrame:
    """
    Assign realistic resource capacities, unit prices, and device types to each device.

    Parameters
    -----------
        df : pd.DataFrame
            DataFrame with devices.
        config : Dict, optional
            Configuration for resource assignment. 
            
            Structure::
            
                {
                    'global': {
                        'group_percentages': {1: 33.0, 2: 33.0, 3: 34.0},  # Percentage of devices in each group
                        'group_ranges': {1: (0, 33), 2: (33, 66), 3: (66, 100)}  # % range for each group
                    },
                    'attributes': {
                        'available_RAM': {
                            'min': 1,
                            'max': 128,
                            'default_price': 0,  # default unit price
                            'price_by_provider_group': {  # optional overrides per provider & group
                                'OPTUS': {1: 3.0, 2: 3.5, 3: 4.0}
                            },
                            'local_distribution': {
                                1: [(60, 0, 60), (40, 60, 100)],
                                2: [(50, 0, 50), (50, 50, 100)],
                                3: [(30, 0, 40), (70, 40, 100)]
                            }
                        },
                        'available_Storage': {'min': 10, 'max': 2000, 'default_price': 0},
                        'available_vCPU': {'min': 1, 'max': 64, 'default_price': 0},
                        'available_GPU': {'min': 0, 'max': 8, 'default_price': 0},
                        'available_TPU': {'min': 0, 'max': 4, 'default_price': 0}
                    },
                    'device_types_by_group': {
                        1: {'CAMERA': 50, 'MOBILE': 45, 'SENSOR': 5},
                        2: {'COMPUTER': 25, 'LAPTOP': 25, 'MOBILE': 25, 'ROUTER': 25},
                        3: {'SERVER': 100}
                    }
                }

    Returns
    -------
        pd.DataFrame
            Dataframe with resource columns and unit prices added.
    """

    rng = np.random.default_rng(seed)

    # -------------------------
    # Default configuration
    # -------------------------
    default_config: Dict[str, Any] = {
        "global": {
            "group_percentages": {1: 33.33, 2: 33.33, 3: 33.34},
            "group_ranges": {1: (0, 33), 2: (33, 66), 3: (66, 100)},
        },
        "attributes": {
            "available_ram_gb": {"min": 1, "max": 128, "default_price": 0.0},
            "available_storage_gb": {"min": 10, "max": 2000, "default_price": 0.0},
            "available_cpu_cores": {"min": 1, "max": 64, "default_price": 0.0},
            "available_gpu_units": {"min": 0, "max": 8, "default_price": 0.0},
            "available_tpu_units": {"min": 0, "max": 4, "default_price": 0.0},
            # Optional network capacities (if you want to constrain placement by bandwidth)
            "available_network_in_mbps": {"min": 10, "max": 10000, "default_price": 0.0},
            "available_network_out_mbps": {"min": 10, "max": 10000, "default_price": 0.0},
        },
        "device_types_by_group": {
            1: {"CAMERA": 50, "MOBILE": 45, "SENSOR": 5},
            2: {"COMPUTER": 25, "LAPTOP": 25, "MOBILE": 25, "ROUTER": 25},
            3: {"SERVER": 100},
        }
    }

    # -------------------------
    # Merge config with defaults
    # -------------------------
    if config is None:
        config = default_config
    else:
        config = dict(config)  # shallow copy

        # Normalize key typo if present in your existing config object
        # (You used 'devices_types_by_group' once; the function expects 'device_types_by_group')
        if "devices_types_by_group" in config and "device_types_by_group" not in config:
            config["device_types_by_group"] = config.pop("devices_types_by_group")

        config.setdefault("global", default_config["global"])
        config["global"].setdefault("group_percentages", default_config["global"]["group_percentages"])
        config["global"].setdefault("group_ranges", default_config["global"]["group_ranges"])

        config.setdefault("attributes", default_config["attributes"])
        for attr, attr_def in default_config["attributes"].items():
            if attr not in config["attributes"]:
                config["attributes"][attr] = attr_def
            else:
                config["attributes"][attr].setdefault("default_price", 0.0)
                config["attributes"][attr].setdefault("price_by_provider_group", {})
                # local_distribution remains optional

        config.setdefault("device_types_by_group", default_config["device_types_by_group"])

    df_result = df.copy()
    n_devices = len(df_result)

    # -------------------------
    # Assign global_group to rows
    # -------------------------
    group_percentages = config["global"]["group_percentages"]
    groups = []
    for group_id, pct in sorted(group_percentages.items()):
        count = int(n_devices * float(pct) / 100.0)
        groups.extend([int(group_id)] * count)

    # Fill remainder (default group 3)
    while len(groups) < n_devices:
        groups.append(3)
    groups = groups[:n_devices]

    rng.shuffle(groups)
    df_result["global_group"] = np.array(groups, dtype=int)

    # -------------------------
    # Assign device_type per group
    # -------------------------
    device_types_by_group = config.get("device_types_by_group", {})
    if device_types_by_group:
        device_types = np.empty(n_devices, dtype=object)
        for group_id in [1, 2, 3]:
            mask = (df_result["global_group"] == group_id)
            group_size = int(mask.sum())
            if group_size == 0:
                continue

            type_probs = device_types_by_group.get(group_id, {})
            if not type_probs:
                type_probs = default_config["device_types_by_group"].get(group_id, {})

            total_pct = sum(type_probs.values())
            if abs(total_pct - 100.0) > 1e-9:
                raise ValueError(
                    f"device_types_by_group for group {group_id} must sum to 100 (got {total_pct})."
                )

            names = list(type_probs.keys())
            probs = np.array(list(type_probs.values()), dtype=float) / 100.0
            device_types[mask.to_numpy()] = rng.choice(names, size=group_size, p=probs)

        df_result["device_type"] = device_types

    # -------------------------
    # Helper: sample values for a group with optional local_distribution
    # -------------------------
    def _sample_group_values(
        group_size: int,
        *,
        min_val: float,
        max_val: float,
        group_range: tuple,
        local_distribution: Optional[list],
    ) -> np.ndarray:
        range_min = min_val + (max_val - min_val) * (group_range[0] / 100.0)
        range_max = min_val + (max_val - min_val) * (group_range[1] / 100.0)

        if local_distribution:
            # local_distribution: list of (pct_devices, pct_min, pct_max)
            sampled = []
            for pct_devices, pct_min, pct_max in local_distribution:
                count = int(group_size * float(pct_devices) / 100.0)
                sub_min = range_min + (range_max - range_min) * (float(pct_min) / 100.0)
                sub_max = range_min + (range_max - range_min) * (float(pct_max) / 100.0)
                if count > 0:
                    sampled.append(rng.uniform(sub_min, sub_max, count))

            if sampled:
                vals = np.concatenate(sampled)
            else:
                vals = np.array([], dtype=float)

            # pad/trim to exact group_size
            if len(vals) < group_size:
                extra = rng.uniform(range_min, range_max, group_size - len(vals))
                vals = np.concatenate([vals, extra])
            vals = vals[:group_size]
            rng.shuffle(vals)
            return vals

        return rng.uniform(range_min, range_max, group_size)

    # -------------------------
    # Assign numeric attributes + unit prices
    # -------------------------
    # IMPORTANT: In the original code, "values" were appended per-group and then assigned
    # to the whole column, which breaks row alignment. Here we fill per-row using masks.
    for attr, attr_config in config["attributes"].items():
        min_val = float(attr_config["min"])
        max_val = float(attr_config["max"])
        base_price = float(attr_config.get("default_price", 0.0))
        price_overrides = attr_config.get("price_by_provider_group", {})
        local_distributions = attr_config.get("local_distribution", {})

        vals = np.zeros(n_devices, dtype=float)

        for group_id in [1, 2, 3]:
            mask = (df_result["global_group"] == group_id)
            group_size = int(mask.sum())
            if group_size == 0:
                continue

            group_range = config["global"]["group_ranges"][group_id]
            local_dist = local_distributions.get(group_id)
            group_vals = _sample_group_values(
                group_size,
                min_val=min_val,
                max_val=max_val,
                group_range=group_range,
                local_distribution=local_dist,
            )
            vals[mask.to_numpy()] = group_vals

        # Capacity columns: use integers for discrete resources
        df_result[attr] = np.floor(vals).astype(int)

        # Unit price column aligned with capacity column
        price_vec = np.full(n_devices, base_price, dtype=float)
        if "provider" in df_result.columns and price_overrides:
            for provider, group_prices in price_overrides.items():
                provider_mask = (df_result["provider"].astype(str).str.upper() == str(provider).upper())
                for group_id, group_price in group_prices.items():
                    mask = provider_mask & (df_result["global_group"] == int(group_id))
                    price_vec[mask.to_numpy()] = float(group_price)

        df_result[f"unit_price_{attr}"] = price_vec

    return df_result

# def assign_device_resources(
#     df: pd.DataFrame,
#     config: Optional[Dict] = None,
#     seed: Optional[int] = None
# ) -> pd.DataFrame:
#   """
#   Assign realistic resource capacities, unit prices, and device types to each device.

#   Parameters
#   -----------
#       df : pd.DataFrame
#           DataFrame with devices.
#       config : Dict, optional
#           Configuration for resource assignment. 
          
#           Structure::
          
#               {
#                   'global': {
#                       'group_percentages': {1: 33.0, 2: 33.0, 3: 34.0},  # Percentage of devices in each group
#                       'group_ranges': {1: (0, 33), 2: (33, 66), 3: (66, 100)}  # % range for each group
#                   },
#                   'attributes': {
#                       'available_RAM': {
#                           'min': 1,
#                           'max': 128,
#                           'default_price': 0,  # default unit price
#                           'price_by_provider_group': {  # optional overrides per provider & group
#                               'OPTUS': {1: 3.0, 2: 3.5, 3: 4.0}
#                           },
#                           'local_distribution': {
#                               1: [(60, 0, 60), (40, 60, 100)],
#                               2: [(50, 0, 50), (50, 50, 100)],
#                               3: [(30, 0, 40), (70, 40, 100)]
#                           }
#                       },
#                       'available_Storage': {'min': 10, 'max': 2000, 'default_price': 0},
#                       'available_vCPU': {'min': 1, 'max': 64, 'default_price': 0},
#                       'available_GPU': {'min': 0, 'max': 8, 'default_price': 0},
#                       'available_TPU': {'min': 0, 'max': 4, 'default_price': 0}
#                   },
#                   'device_types_by_group': {
#                       1: {'CAMERA': 50, 'MOBILE': 45, 'SENSOR': 5},
#                       2: {'COMPUTER': 25, 'LAPTOP': 25, 'MOBILE': 25, 'ROUTER': 25},
#                       3: {'SERVER': 100}
#                   }
#               }

#   Returns
#   -------
#       pd.DataFrame
#           Dataframe with resource columns and unit prices added.
#   """

#   if seed is not None:
#       np.random.seed(seed)

#   # Default configuration
#   default_config = {
#       'global': {
#           'group_percentages': {1: 33.33, 2: 33.33, 3: 33.34},
#           'group_ranges': {1: (0, 33), 2: (33, 66), 3: (66, 100)}
#       },
#       'attributes': {
#           'available_RAM': {'min': 1, 'max': 128, 'default_price': 0},
#           'available_Storage': {'min': 10, 'max': 2000, 'default_price': 0},
#           'available_vCPU': {'min': 1, 'max': 64, 'default_price': 0},
#           'available_GPU': {'min': 0, 'max': 8, 'default_price': 0},
#           'available_TPU': {'min': 0, 'max': 4, 'default_price': 0}
#       },
#       'device_types_by_group': {
#           1: {'CAMERA': 50, 'MOBILE': 45, 'SENSOR': 5},
#           2: {'COMPUTER': 25, 'LAPTOP': 25, 'MOBILE': 25, 'ROUTER': 25},
#           3: {'SERVER': 100}
#       }
#   }

#   # Use provided configuration or default
#   if config is None:
#       config = default_config
#   else:
#       if 'global' not in config:
#           config['global'] = default_config['global']
#       else:
#           if 'group_percentages' not in config['global']:
#               config['global']['group_percentages'] = default_config['global']['group_percentages']
#           else:
#               configured_groups = config['global']['group_percentages']
#               total_pct = sum(configured_groups.values())
#               if total_pct < 100:
#                   remaining = 100 - total_pct
#                   unconfigured = [g for g in [1, 2, 3] if g not in configured_groups]
#                   if unconfigured:
#                       split = remaining / len(unconfigured)
#                       for g in unconfigured:
#                           config['global']['group_percentages'][g] = split

#           if 'group_ranges' not in config['global']:
#               config['global']['group_ranges'] = default_config['global']['group_ranges']

#       if 'attributes' not in config:
#           config['attributes'] = default_config['attributes']
#       else:
#           for attr in default_config['attributes']:
#               if attr not in config['attributes']:
#                   config['attributes'][attr] = default_config['attributes'][attr]
#               else:
#                   config['attributes'][attr].setdefault('default_price', 0)
#                   config['attributes'][attr].setdefault('price_by_provider_group', {})

#       if 'device_types_by_group' not in config:
#           config['device_types_by_group'] = default_config['device_types_by_group']

#   df_result = df.copy()
#   n_devices = len(df_result)

#   # Assign global groups to each device
#   group_percentages = config['global']['group_percentages']
#   groups = []
#   for group, percentage in sorted(group_percentages.items()):
#       count = int(n_devices * percentage / 100)
#       groups.extend([group] * count)

#   while len(groups) < n_devices:
#       groups.append(3)
#   groups = groups[:n_devices]

#   np.random.shuffle(groups)
#   df_result['global_group'] = groups

#   # Assign device types per group using configured probabilities
#   device_types_by_group = config.get('device_types_by_group', {})
#   if device_types_by_group:
#       device_types = np.empty(n_devices, dtype=object)
#       for group in [1, 2, 3]:
#           group_mask = df_result['global_group'] == group
#           group_size = group_mask.sum()
#           if group_size == 0:
#               continue

#           type_probs = device_types_by_group.get(group, {})
#           if not type_probs:
#               type_probs = default_config['device_types_by_group'].get(group, {})

#           total_pct = sum(type_probs.values())
#           if total_pct != 100:
#               raise ValueError(
#                   f"device_types_by_group for group {group} must sum to 100 (got {total_pct})."
#               )

#           type_names = list(type_probs.keys())
#           probabilities = np.array(list(type_probs.values()), dtype=float) / 100.0
#           assigned = np.random.choice(type_names, size=group_size, p=probabilities)
#           device_types[group_mask] = assigned

#       df_result['device_type'] = device_types

#   # Process numeric attributes (all configured attributes)
#   integer_attrs = list(config['attributes'].keys())

#   for attr in integer_attrs:
#       attr_config = config['attributes'][attr]
#       min_val = attr_config['min']
#       max_val = attr_config['max']
#       base_price = attr_config.get('default_price', 0)
#       price_overrides = attr_config.get('price_by_provider_group', {})

#       values = []

#       for group in [1, 2, 3]:
#           group_mask = df_result['global_group'] == group
#           group_size = group_mask.sum()

#           if group_size == 0:
#               continue

#           group_range = config['global']['group_ranges'][group]
#           range_min = min_val + (max_val - min_val) * group_range[0] / 100
#           range_max = min_val + (max_val - min_val) * group_range[1] / 100

#           if 'local_distribution' in attr_config and group in attr_config['local_distribution']:
#               local_dist = attr_config['local_distribution'][group]
#               group_values = []

#               for pct_devices, pct_min, pct_max in local_dist:
#                   count = int(group_size * pct_devices / 100)
#                   sub_min = range_min + (range_max - range_min) * pct_min / 100
#                   sub_max = range_min + (range_max - range_min) * pct_max / 100

#                   sub_values = np.random.uniform(sub_min, sub_max, count)
#                   group_values.extend(sub_values)

#               while len(group_values) < group_size:
#                   group_values.append(np.random.uniform(range_min, range_max))
#               group_values = group_values[:group_size]

#           else:
#               group_values = np.random.uniform(range_min, range_max, group_size)

#           values.extend(group_values)

#       df_result[attr] = np.array(values, dtype=int)

#       # Build unit price vector with defaults and overrides per provider/group
#       price_values = np.full(n_devices, base_price, dtype=float)
#       for provider, group_prices in price_overrides.items():
#           provider_mask = df_result['provider'].str.upper() == provider.upper()
#           for group_id, group_price in group_prices.items():
#               mask = provider_mask & (df_result['global_group'] == int(group_id))
#               price_values[mask] = group_price

#       df_result[f"unit_price_{attr}"] = price_values

#   return df_result