"""
Generators Subpackage

This subpackage contains all generator functions for creating topologies,
pricing configurations, and problem instances.

Modules
-------
- topology: Functions for generating device topologies within geographic areas
- pricing: Functions for generating pricing YAML files from topologies
- problem_instance: Functions for generating problem instances from pricing and user requests
- client_demand: Functions for generating hardware demand from user locations
"""

from .topology import topology
from .pricing import pricing_from_topology, compatible_provider_groups_from_offer
from .problem_instance import problem_instance
from . import client_demand

__all__ = [
    # Topology Generator
    'topology',
    
    # Pricing Generator
    'pricing_from_topology',
    'compatible_provider_groups_from_offer'
    
    # Problem Instance
    'problem_instance',

    # Demand Generator
    'client_demand',
]
