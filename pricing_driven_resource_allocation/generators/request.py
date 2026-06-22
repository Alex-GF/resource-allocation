from typing import Dict, Any

def request(
    topology_demand: Dict[str, Any],
    topology_request: Dict[str, Any],
    users_demand: Dict[str, Any],
    resources_to_consider: list[str],
    *,
    currency: str = "USD",
    resource_mapping: Dict[str, str] | None = None,
) -> Dict[str, Any]:
    """
    Build a request object dynamically, aligning:
      - keys in request["resources"] with the offer resource vocabulary (offer_resources keys)
      - values with the demand output (users_demand), via a configurable mapping

    Parameters
    ----------
    topology_demand : dict
        Must contain 'zone' for users_location.
    topology_request : dict
        Must contain providers_to_consider, budget, max_devices, devices_types_required, max_distance.
    users_demand : dict
        Output from calculate_resources (demand generator).
    resources_to_consider : list[str]
        List of resource keys to consider in the request.
    currency : str
        Currency code.
    resource_mapping : dict, optional
        Maps offer resource key -> users_demand key.
        If None, a sensible default mapping for the new metrics is used.

    Returns
    -------
    dict
        Request payload.
    """

    # Default mapping aligned with the updated demand generator and updated offer vocabulary.
    default_mapping = {
        "available_ram_gb": "ram_total_gb",
        "available_storage_gb": "storage_total_gb",
        "available_cpu_cores": "cpu_total_cores",
        "available_gpu_units": "gpu_equivalent_units",
        "available_tpu_units": "tpu_equivalent_units",
        "available_network_in_mbps": "network_megabits_in_per_second",
        "available_network_out_mbps": "network_megabits_out_per_second",
    }

    if resource_mapping is None:
        resource_mapping = default_mapping
    else:
        # allow partial override while keeping defaults
        merged = dict(default_mapping)
        merged.update(resource_mapping)
        resource_mapping = merged

    # Determine offer vocabulary keys (resources defined in offer generation).
    # If you pass OFFER_CONFIGURATION["attributes"], this is already the correct key set.

    # Build resources block dynamically
    resources_block: Dict[str, Any] = {}
    for offer_key in resources_to_consider:
        demand_key = resource_mapping.get(offer_key)

        # If the offer defines a resource we do not have a mapping/value for, default to 0.
        # This keeps the request structurally compatible with the offer vocabulary.
        if demand_key is None:
            resources_block[offer_key] = 0
            continue

        resources_block[offer_key] = users_demand.get(demand_key, 0)

    request = {
        "currency": currency,
        "users_location": topology_demand["zone"],
        "providers_to_consider": topology_request["providers_to_consider"],
        "budget": topology_request["budget"],
        "max_devices": topology_request["max_devices"],
        "device_types": topology_request["devices_types_required"],
        "resources": resources_block,
        "max_distance": topology_request["max_distance"],
    }

    return request