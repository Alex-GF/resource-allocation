"""
Yaml Utilities Module

This module provides functions to convert between YAML files and pricing proto objects.
"""

from typing import Optional
import yaml
from google.protobuf import json_format

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