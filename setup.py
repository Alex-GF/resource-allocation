"""Setup configuration for pricing-driven-service-allocation package."""

from setuptools import setup, find_packages

with open("pricing_driven_service_allocation/README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="pricing-driven-service-allocation",
    version="1.0.0",
    author="Alejandro",
    description="A package for managing device topologies, resource allocation, and pricing for service allocation problems",
    long_description=long_description,
    long_description_content_type="text/markdown",
    packages=find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.7",
    install_requires=[
        "pandas>=1.3.0",
        "numpy>=1.21.0",
        "shapely>=1.8.0",
        "pyyaml>=5.4.0",
        "protobuf>=3.19.0",
    ],
)
