import math
from typing import Dict, Any, List
from app.models.schemas import SpillFingerprint

def polygon_area_and_centroid(coords: List[List[float]]) -> tuple[float, float, float]:
    """Shoelace formula for polygon area and centroid in deg coordinates."""
    n = len(coords)
    if n < 3:
        return 0.0, coords[0][1] if n else 0.0, coords[0][0] if n else 0.0
    
    area_deg = 0.0
    cx = 0.0
    cy = 0.0
    for i in range(n - 1):
        xi, yi = coords[i][0], coords[i][1]
        x_next, y_next = coords[i+1][0], coords[i+1][1]
        factor = (xi * y_next - x_next * yi)
        area_deg += factor
        cx += (xi + x_next) * factor
        cy += (yi + y_next) * factor
        
    area_deg = abs(area_deg) / 2.0
    if area_deg > 0:
        cx = cx / (6.0 * (area_deg if area_deg > 0 else 1.0))
        cy = cy / (6.0 * (area_deg if area_deg > 0 else 1.0))
    else:
        cx = sum(c[0] for c in coords) / n
        cy = sum(c[1] for c in coords) / n
        
    return area_deg, cy, cx

def analyze_spill_fingerprint(spill_id: str, geojson_geom: Dict[str, Any]) -> SpillFingerprint:
    """
    Computes rigorous spatial geometry fingerprint descriptors for an observed spill polygon.
    Works natively in pure Python with or without Shapely.
    """
    coords = []
    if geojson_geom["type"] == "Polygon":
        coords = geojson_geom["coordinates"][0]
    elif geojson_geom["type"] == "MultiPolygon":
        coords = geojson_geom["coordinates"][0][0]
        
    # Area & centroid
    area_deg, centroid_lat, centroid_lon = polygon_area_and_centroid(coords)
    
    lat_rad = math.radians(centroid_lat)
    km_per_deg_lat = 111.0
    km_per_deg_lon = 111.0 * math.cos(lat_rad)
    
    # Calculate perimeter in km
    perimeter_km = 0.0
    for i in range(len(coords) - 1):
        dx_km = (coords[i+1][0] - coords[i][0]) * km_per_deg_lon
        dy_km = (coords[i+1][1] - coords[i][1]) * km_per_deg_lat
        perimeter_km += math.hypot(dx_km, dy_km)
        
    area_km2 = area_deg * km_per_deg_lat * km_per_deg_lon
    
    # Compactness (Isoperimetric Quotient: 4 * pi * Area / Perimeter^2)
    compactness = (4 * math.pi * area_km2) / (perimeter_km ** 2) if perimeter_km > 0 else 0.0
    
    # Bounding box dimensions & orientation
    lons = [c[0] for c in coords]
    lats = [c[1] for c in coords]
    
    min_lon, max_lon = min(lons), max(lons)
    min_lat, max_lat = min(lats), max(lats)
    
    width_deg = max_lon - min_lon
    height_deg = max_lat - min_lat
    
    dx_total = width_deg * km_per_deg_lon
    dy_total = height_deg * km_per_deg_lat
    
    length_km = max(dx_total, dy_total)
    width_km = min(dx_total, dy_total) if min(dx_total, dy_total) > 0 else length_km * 0.4
    aspect_ratio = length_km / max(width_km, 0.01)
    
    # Orientation Angle in degrees
    orientation_deg = math.degrees(math.atan2(dy_total, dx_total)) % 180.0

    return SpillFingerprint(
        spill_id=spill_id,
        area_km2=round(area_km2, 3),
        perimeter_km=round(perimeter_km, 3),
        centroid_lat=round(centroid_lat, 5),
        centroid_lon=round(centroid_lon, 5),
        orientation_deg=round(orientation_deg, 1),
        length_km=round(length_km, 3),
        width_km=round(width_km, 3),
        compactness=round(compactness, 4),
        aspect_ratio=round(aspect_ratio, 2),
        boundary_points=[[round(c[0], 5), round(c[1], 5)] for c in coords]
    )
