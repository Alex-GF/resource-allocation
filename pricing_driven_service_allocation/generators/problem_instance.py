"""
Problem Instance Module

This module provides functions for generating problem instances from pricing and user requests.
"""

import os
import pandas as pd
from typing import Tuple

def resolve_price(addon_details, resources: dict) -> float:
    """
    Evaluate a price expression by replacing resource placeholders with actual values.

    Parameters
    ----------
    addon_details : AddOn
        The add-on details containing the price expression.
    resources : dict
        A dictionary with resource values to replace in the expression.
    Returns
    -------
    float
        The evaluated price.
    """
    from iPricing.model.iPricing_pb2 import AddOn
    
    details_copy = AddOn()
    details_copy.CopyFrom(addon_details)
    
    for resource_key, resource_value in addon_details.usageLimitsExtensions.items():
        if resource_key not in resources.keys():
            placeholder = f"#{resource_key}"
            details_copy.price.string_value = details_copy.price.string_value.replace(placeholder, str(resource_value.value.number_value))
    
    for resource_key, resource_value in resources.items():
        placeholder = f"#{resource_key}"
        
        if not details_copy.usageLimitsExtensions.get(resource_key):
            details_copy.price.string_value = details_copy.price.string_value.replace(placeholder, "0")
        # If requested resource exceeds add-on limit, price must be capped to the limit
        else: 
            if details_copy.usageLimitsExtensions[resource_key].value.number_value < resource_value:
                resource_value = details_copy.usageLimitsExtensions[resource_key].value.number_value
            details_copy.price.string_value = details_copy.price.string_value.replace(placeholder, str(resource_value))
    
    try:
        evaluated_price = eval(details_copy.price.string_value)
        return evaluated_price
    except Exception as e:
        print(f"Error evaluating price expression '{details_copy.price.string_value}': {e}")
        return float('inf')  # Assign a high price on error


def problem_instance(
    instance_pricing,
    request: dict,
    topologies_result_dir: str,
    unlimited_value: int = 100000000,
    options: dict = {'save_pricing': False, 'output_path': './generated_pricing.yml'}
) -> Tuple:
    """
    Merge a user request with a pricing instance representing a topology 
    to generate a pricing that can be optimized.

    Parameters
    ----------
    instance_pricing : Pricing
        The pricing instance to be considered (represents a topology).
    request : dict
        The user request object containing problem specifications. 
        
        Structure::
        
            {
                'currency': 'USD', # Currency to be considered
                'users_location': [
                    (lon1, lat1),  # Longitude, Latitude
                    (lon2, lat2),  # Longitude, Latitude
                    ...
                ],
                'providers_to_consider': [
                    'telstra'
                ],
                'budget': int,
                'max_devices': int, # If not set, 'max_devices' = total_devices
                'device_types': [str, str, ...], # e.g., ['SENSOR', 'CAMERA']
                'resources': {
                    'available_ram': int,      # in GB          | if not provided defaults to 0
                    'available_storage': int,  # in GB          | if not provided defaults to 0
                    'available_vcpu': int,     # amount of vCPU | if not provided defaults to 0
                    'available_gpu': int,      # amount of GPU  | if not provided defaults to 0
                    'available_tpu': int,      # amount of TPU  | if not provided defaults to 0
                },
                'max_distance': int,  # in meters
            }
            
        **NOTE:** The location defines an area where users are expected to be using 
        the system. It'll be used to compute distance from the devices.
        
    topologies_result_dir : str
        Directory where topology results are stored.
    unlimited_value : int, optional
        Value to use for unlimited resources. Default is 100000000.
    options : dict, optional
        Options for saving the generated pricing.
        
    Returns
    -------
    Tuple[Pricing, str]
        A tuple containing:
            - A new Pricing object representing the problem instance.
            - A filter required by the CSOP solver to optimize the solution based on user request.
    """
    from iPricing.model.iPricing_pb2 import Pricing
    from ..utils import point_in_polygon, distance_to_farthest_edge, haversine
  
    pricing_to_resolve = Pricing()
    pricing_to_resolve.CopyFrom(instance_pricing)

    if 'currency' in request:
        pricing_to_resolve.currency = request.get('currency')
    else:
        raise ValueError("Request must specify 'currency' field.")

    # Load topology devices data using saasName (topology_id)
    topology_id = instance_pricing.saasName
    topology_dir = os.path.join(topologies_result_dir, topology_id)
    devices_csv_path = os.path.join(topology_dir, "devices.csv")
    
    if not os.path.exists(devices_csv_path):
        raise FileNotFoundError(f"Topology devices file not found: {devices_csv_path}")
    
    topology_devices_df = pd.read_csv(devices_csv_path, index_col=0)
    
    # Get users location polygon
    users_location = request.get('users_location', [])

    # 1. Keep only devices (add-ons) from providers_to_consider 
    allowed_addon_ids = set()
    for addon_name, addon_details in instance_pricing.addOns.items():    
        provider = addon_name.split('_')[0]
        
        # Filter devices whose provider is not in providers_to_consider
        if 'providers_to_consider' in request:
            if provider.lower() not in [p.lower() for p in request['providers_to_consider']]:
                continue
            
        # Compute price based on user requirements
        addon_details.price.number_value = resolve_price(addon_details, request['resources'])
        
        # Calculate distance attribute
        device_id = int(addon_name.split('_')[1])
        if device_id in topology_devices_df.index:
            device_row = topology_devices_df.loc[device_id]
            device_lat = device_row['latitude']
            device_lon = device_row['longitude']
            
            # Calculate distance
            if users_location and len(users_location) >= 3:
                # Check if device is inside polygon
                if point_in_polygon(device_lat, device_lon, users_location):
                    distance_meters = 0.0
                else:
                    # Calculate distance to farthest edge
                    distance_meters = distance_to_farthest_edge(device_lat, device_lon, users_location)
            else:
                # If no valid polygon, assume distance is 0
                distance_meters = 0.0
            
            # Transform distance for CSP solver: higher is better
            distance_value = unlimited_value - distance_meters
        else:
            # Device not found in topology, set default distance
            distance_value = unlimited_value
        
        # Add distance to usageLimitsExtensions
        addon_details.usageLimitsExtensions['distance'].value.number_value = int(distance_value)
        
        # Save allowed add-ons
        allowed_addon_ids.add(addon_name)

    # 2. Remove disallowed add-ons from pricing_to_resolve
    pricing_to_resolve.addOns.clear()
    for addon_name in allowed_addon_ids:
        pricing_to_resolve.addOns[addon_name].CopyFrom(instance_pricing.addOns[addon_name])
        
    # 3. Remove add-ons from excludes that are no longer present
    for addon_name, addon_details in pricing_to_resolve.addOns.items():
        filtered_excludes = [
            ex for ex in addon_details.excludes if ex in allowed_addon_ids
        ]
        del addon_details.excludes[:]
        addon_details.excludes.extend(filtered_excludes)
        
    # 4. Generate filter with remaining constraints
    filter_criteria = {}
    if 'budget' in request:
        filter_criteria['maxPrice'] = request['budget']
    
    if 'max_devices' in request:
        filter_criteria['maxSubscriptionSize'] = request['max_devices']
    
    if 'resources' in request:
        # Resources expected in fixed order:
        filter_criteria['usageLimits'] = request.get('resources', {})
    
    # Add distance to usageLimits in filter criteria
    max_distance = request.get('max_distance', 0)
    if 'usageLimits' not in filter_criteria:
        filter_criteria['usageLimits'] = {}
    filter_criteria['usageLimits']['distance'] = unlimited_value - max_distance
    
    # Add device_types to features in filter criteria
    if 'device_types' in request:
        filter_criteria['features'] = request['device_types']
    
    return (pricing_to_resolve, filter_criteria)
