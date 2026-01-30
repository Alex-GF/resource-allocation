"""
Pricing-Driven Service Allocation Package

A comprehensive package for managing device topologies, resource allocation,
and pricing for service allocation problems.

Modules
-------
- dataset: Subpackage for data loading and transformation
  - load: Functions for loading device datasets
  - transform: Functions for filtering and assigning resources to devices
  
- generators: Subpackage containing all generator functions
  - topology_generator: Functions for generating device topologies
  - pricing_generator: Functions for generating pricing YAML files
  - problem_instance: Functions for generating problem instances
  
- utils: Subpackage with utility functions
  - yaml_utils: Functions for handling tranformation from YAML files to pricing proto objects
  - geometrical_utils: Functions for geographical calculations
"""

# Import generators subpackage
from . import dataset
from . import generators
from . import utils

__version__ = '1.0.0'
__author__ = 'Alejandro'

__all__ = [
    # Data Management
    'dataset',
    
    # Generators subpackage
    'generators',
    
    # Utilities subpackage
    'utils',
]
