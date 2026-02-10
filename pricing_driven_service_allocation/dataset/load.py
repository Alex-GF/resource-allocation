"""
Data Loading Module

This module provides functions for loading device datasets.
"""

import pandas as pd

def load_devices_dataframe(path: str) -> pd.DataFrame:
    """
    Reads the CSV and returns a DataFrame with the required columns.
    
    Parameters
    ----------
    path : str
        Path to the devices CSV file.
    
    Returns
    -------
    pd.DataFrame
        DataFrame with standardized device information.
    """
    df = pd.read_csv(path)
    
    # Rename columns for consistency
    df.rename(
        columns={
            "SITE_ID": "device_id",
            "LATITUDE": "latitude",
            "LONGITUDE": "longitude",
            "NAME": "name",
            "STATE": "state",
            "LICENSING_AREA_ID": "licensing_area_id",
            "POSTCODE": "postcode",
            "SITE_PRECISION": "site_precision",
            "ELEVATION": "elevation",
            "HCIS_L2": "hcis_l2",
        },
        inplace=True,
    )
    
    # Set device_id as index
    df.set_index("device_id", inplace=True, drop=False)
    
    # Remove unnecessary columns if any exist
    df = df[
        [
            "name",
            "latitude",
            "longitude",
            "elevation",
        ]
    ]
    
    return df


def load_c_locations_dataframe(path: str) -> pd.DataFrame:
    """
    Reads the CSV and returns a DataFrame with the required columns.

    Parameters
    ----------
    path : str
        Path to the devices CSV file.

    Returns
    -------
    pd.DataFrame
        DataFrame with standardized device information.
    """
    df = pd.read_csv(path)

    # Rename columns for consistency
    df.rename(
        columns={
            "IP": "client_ip_address",
            "Latitude": "latitude",
            "Longitude": "longitude",
            "PostCode": "zip",
            "City": "city",
            "State": "state",
            "Country": "country",
        },
        inplace=True,
    )

    # Set client_id as index
    # df.insert(0, 'client_id', range(0, len(df)))
    # df.set_index("id", inplace=True, drop=False)

    df.drop(["country", "zip", "city", "state", "client_ip_address"], axis=1, inplace=True)

    return df