"""
AEGIS-SPILL Mask Polygonizer
Converts binary SAR U-Net prediction masks into GeoJSON Polygons and spatial coordinates
for fingerprint analysis and interactive WebGIS mapping.
"""
import math
from typing import List, Tuple, Dict, Any, Optional
import numpy as np


def extract_mask_boundary_pixels(mask: np.ndarray) -> List[Tuple[int, int]]:
    """
    Extracts ordered perimeter coordinates of the primary connected slick component.
    Works natively with NumPy without external C-extensions.
    """
    if mask.sum() == 0:
        return []

    # Pad mask to safely trace boundary
    h, w = mask.shape
    padded = np.pad(mask, 1, mode="constant", constant_values=0)

    # Simple 4-neighborhood boundary detection
    # A pixel is on the boundary if it is 1 and has at least one 0 neighbor
    interior = (
        (padded[1:-1, 1:-1] == 1) &
        (padded[0:-2, 1:-1] == 1) &
        (padded[2:, 1:-1] == 1) &
        (padded[1:-1, 0:-2] == 1) &
        (padded[1:-1, 2:] == 1)
    )
    boundary_mask = (mask == 1) & (~interior)
    boundary_indices = np.argwhere(boundary_mask)

    if len(boundary_indices) < 3:
        # Fallback to all positive pixels
        boundary_indices = np.argwhere(mask == 1)

    if len(boundary_indices) < 3:
        return []

    # Sort boundary pixels angularly around centroid to form a closed, uncrossed polygon
    centroid_r = np.mean(boundary_indices[:, 0])
    centroid_c = np.mean(boundary_indices[:, 1])

    angles = np.arctan2(
        boundary_indices[:, 0] - centroid_r,
        boundary_indices[:, 1] - centroid_c
    )
    sorted_idx = np.argsort(angles)
    sorted_coords = boundary_indices[sorted_idx]

    # Downsample points for efficient GeoJSON polygon representation (max 32 vertices)
    n_points = len(sorted_coords)
    step = max(1, n_points // 32)
    decimated = sorted_coords[::step].tolist()

    # Close loop
    if decimated and decimated[0] != decimated[-1]:
        decimated.append(decimated[0])

    return decimated


def mask_to_geojson_polygon(
    mask: np.ndarray,
    center_lat: float = 28.6500,
    center_lon: float = -89.4200,
    km_span: float = 15.0,
) -> Optional[Dict[str, Any]]:
    """
    Converts binary prediction mask to GeoJSON Polygon geometry in WGS84 coordinates.
    Maps pixel grid [0, H] x [0, W] to geographic space around (center_lat, center_lon).
    """
    boundary_px = extract_mask_boundary_pixels(mask)
    if len(boundary_px) < 3:
        return None

    h, w = mask.shape
    km_per_deg_lat = 111.0
    km_per_deg_lon = 111.0 * math.cos(math.radians(center_lat))

    # Compute deg offsets per pixel
    d_lat_per_pixel = (km_span / km_per_deg_lat) / h
    d_lon_per_pixel = (km_span / km_per_deg_lon) / w

    coords = []
    for r, c in boundary_px:
        # Origin at center
        dy = (h / 2.0 - r) * d_lat_per_pixel
        dx = (c - w / 2.0) * d_lon_per_pixel
        lon = round(center_lon + dx, 5)
        lat = round(center_lat + dy, 5)
        coords.append([lon, lat])

    if coords and coords[0] != coords[-1]:
        coords.append(coords[0])

    return {
        "type": "Polygon",
        "coordinates": [coords]
    }
