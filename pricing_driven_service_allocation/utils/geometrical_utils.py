"""
Utilities Module

This module provides utility functions for distance calculations and geometric operations.
"""

from math import radians, cos, sin, asin, sqrt
import pandas as pd
from typing import Tuple, List
from shapely.geometry import Point, Polygon


def haversine(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    """
    Calculate the great circle (horizontal) distance between two points
    on the earth (specified in decimal degrees). Returns distance in meters.
    
    Parameters
    ----------
    lon1 : float
        Longitude of first point in decimal degrees.
    lat1 : float
        Latitude of first point in decimal degrees.
    lon2 : float
        Longitude of second point in decimal degrees.
    lat2 : float
        Latitude of second point in decimal degrees.
    
    Returns
    -------
    float
        Distance in meters.
    """
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    c = 2 * asin(sqrt(a))
    km = 6371 * c
    return km * 1000


def distance_3d(lon1: float, lat1: float, lon2: float, lat2: float, elev1: float = 0.0, elev2: float = 0.0) -> float:
    """
    Compute 3D distance between two points considering horizontal haversine distance
    and vertical elevation difference (meters). NaN elevations are treated as 0.
    
    Parameters
    ----------
    lon1 : float
        Longitude of first point in decimal degrees.
    lat1 : float
        Latitude of first point in decimal degrees.
    lon2 : float
        Longitude of second point in decimal degrees.
    lat2 : float
        Latitude of second point in decimal degrees.
    elev1 : float, optional
        Elevation of first point in meters. Default is 0.0.
    elev2 : float, optional
        Elevation of second point in meters. Default is 0.0.
    
    Returns
    -------
    float
        3D distance in meters.
    """
    # Treat NaN elevations as 0
    elev1 = 0.0 if pd.isna(elev1) else float(elev1)
    elev2 = 0.0 if pd.isna(elev2) else float(elev2)
    d_horizontal = haversine(lon1, lat1, lon2, lat2)
    d_vertical = elev2 - elev1
    return (d_horizontal ** 2 + d_vertical ** 2) ** 0.5


def point_in_polygon(lat: float, lon: float, polygon_coords: List[Tuple[float, float]]) -> bool:
    """
    Check if a point is inside a polygon.
    
    Parameters
    ----------
    lat : float
        Latitude of the point
    lon : float
        Longitude of the point
    polygon_coords : List[Tuple[float, float]]
        List of (lon, lat) tuples defining the polygon
        
    Returns
    -------
    bool
        True if point is inside polygon, False otherwise
    """
    point = Point(lon, lat)
    polygon = Polygon(polygon_coords)
    return polygon.contains(point)


def distance_to_farthest_edge(lat: float, lon: float, polygon_coords: List[Tuple[float, float]]) -> float:
    """
    Calculate the maximum distance from a point to any edge of a polygon.
    
    Parameters
    ----------
    lat : float
        Latitude of the point
    lon : float
        Longitude of the point
    polygon_coords : List[Tuple[float, float]]
        List of (lon, lat) tuples defining the polygon
        
    Returns
    -------
    float
        Maximum distance in meters from the point to any vertex of the polygon
    """
    max_distance = 0.0
    for vertex_lon, vertex_lat in polygon_coords:
        dist = haversine(lon, lat, vertex_lon, vertex_lat)
        if dist > max_distance:
            max_distance = dist
    return max_distance
