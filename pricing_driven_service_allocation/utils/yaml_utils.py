"""
Yaml Utilities Module

This module provides functions to convert between YAML files and pricing proto objects.
"""

from typing import Optional
import yaml
from google.protobuf import json_format
import json
from typing import List, Tuple

def yaml_to_pricing_proto(yaml_path: str, message_type):
    """
    Convert a YAML file to a Protocol Buffer message.
    
    Parameters
    ----------
    yaml_path : str
        Path to the YAML file.
    message_type : type
        The Protocol Buffer message type to convert to.
    
    Returns
    -------
    message
        The Protocol Buffer message instance.
    """
    # Read the YAML file
    yaml_str = ""
    with open(yaml_path, 'r', encoding='utf-8') as f:
        yaml_str = f.read()
  
    # Load YAML into a Python dictionary
    data = yaml.safe_load(yaml_str)
    
    # Create an empty instance of the message
    message = message_type()
    
    # Map the dictionary to the Proto object
    # ignore_unknown_fields=True is useful if the YAML has extras not defined in the proto
    json_format.ParseDict(data, message, ignore_unknown_fields=True)

    return message


def find_identical_addons(pricing_obj) -> List[Tuple[str, str]]:
    """
    Find pairs of add-ons in a Pricing proto that are exactly equal in content
    (ignoring the add-on key/name itself).

    Parameters
    ----------
    pricing_obj : Pricing
        A Pricing protocol buffer object (generated from iPricing.proto)

    Returns
    -------
    List[Tuple[str, str]]
        List of tuples with the names of add-ons that are identical.
        Returns an empty list if no identical add-ons are found.
    """
    # Support either a proto Message or a plain dict produced by MessageToDict
    if isinstance(pricing_obj, dict):
        pricing_dict = pricing_obj
    else:
        # Convert proto message to dict using stable field names
        pricing_dict = json_format.MessageToDict(pricing_obj, preserving_proto_field_name=True)

    # Try both common key styles: 'addOns' (proto camelCase) and 'add_ons' (python/snaked)
    addons_block = pricing_dict.get('addOns') or pricing_dict.get('add_ons') or {}
    if not addons_block:
        return []

    # Convert each addOn entry to a dict for structural comparison
    addon_dicts = {}
    for name, addon in addons_block.items():
        # addon may already be a dict (when pricing_dict comes from MessageToDict)
        if isinstance(addon, dict):
            d = dict(addon)
        else:
            # Fallback: try to convert proto message to dict
            d = json_format.MessageToDict(addon, preserving_proto_field_name=True)
        # remove the name field if present in the dict representation
        d.pop('name', None)
        addon_dicts[name] = d

    # Compute a canonical JSON signature for each add-on for robust comparison.
    def _normalize(obj):
        # Recursively normalize data structures so semantically equal
        # objects produce identical representations.
        if isinstance(obj, dict):
            new = {}
            for k in sorted(obj.keys()):
                v = obj[k]
                nv = _normalize(v)
                # Skip empty containers to avoid superficial differences
                if nv == {} or nv == []:
                    # keep empty if key is meaningful
                    new[k] = nv
                else:
                    new[k] = nv
            return new
        if isinstance(obj, list):
            # Normalize items and sort by their JSON representation to make order-insensitive
            normalized_items = [_normalize(i) for i in obj]
            try:
                sorted_items = sorted(normalized_items, key=lambda x: json.dumps(x, sort_keys=True, separators=(",", ":")))
            except TypeError:
                # Fallback if elements not JSON-serializable keys; keep original order
                sorted_items = normalized_items
            return sorted_items
        # Normalize numeric types: floats that are integral -> ints
        if isinstance(obj, float):
            if abs(obj - round(obj)) < 1e-9:
                return int(round(obj))
            return obj
        return obj

    signatures = {}
    for name, d in addon_dicts.items():
        canon = _normalize(d)
        sig = json.dumps(canon, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        signatures[name] = sig

    # Collect identical pairs by signature
    rev: Dict[str, list] = {}
    for name, sig in signatures.items():
        rev.setdefault(sig, []).append(name)

    identical_pairs: List[Tuple[str, str]] = []
    for names in rev.values():
        if len(names) > 1:
            names_sorted = sorted(names)
            for i in range(len(names_sorted)):
                for j in range(i + 1, len(names_sorted)):
                    identical_pairs.append((names_sorted[i], names_sorted[j]))

    return identical_pairs

def pricing_proto_to_yaml(pricing_obj, yaml_path: str, options: Optional[dict] = {}) -> None:
    """
    Save a Pricing Protocol Buffer object to a YAML file.
    
    Parameters
    ----------
    pricing_obj : Pricing
        The Pricing Protocol Buffer object to save.
    yaml_path : str
        Path where the YAML file will be saved.
    options : dict, optional
        Additional options for YAML generation.
          - 'logs': bool, whether to print detailed logs during generation (default: True)
    """
    output_path = yaml_path
    with open(output_path, 'w', encoding='utf-8') as f:
        yaml.dump(
            json_format.MessageToDict(pricing_obj, preserving_proto_field_name=True),
            f,
            default_flow_style=False,
            allow_unicode=True,
            sort_keys=False
        )
    if options.get('logs', True):
        print(f"Generated pricing saved to: {output_path}")