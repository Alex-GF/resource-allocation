"""
Utils Subpackage

This subpackage contains all utility functions for distance calculations,
geometric operations, yaml I/O, and other helper functions.

Modules
-------
  - yaml_utils: Functions for handling transformations from YAML to pricing proto objects.
  - geometrical_utils: Functions for handling geometrical calculations.
"""

from .yaml_utils import (
  yaml_to_pricing_proto,
  pricing_proto_to_yaml,
  find_identical_addons
)

from .geometrical_utils import (
  haversine,
  distance_3d,
  point_in_polygon,
  distance_to_farthest_edge
)

__all__ = [
    # YAML Utilities
    'yaml_to_pricing_proto',
    'pricing_proto_to_yaml',
    'find_identical_addons'
    
    # Geometrical Utilities
    'haversine',
    'distance_3d',
    'point_in_polygon',
    'distance_to_farthest_edge',
]
