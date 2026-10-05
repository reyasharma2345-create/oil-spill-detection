import math
import numpy as np
from typing import Dict, Any
from app.modules.environment.forcing_grid import EnvironmentalForcing
from app.models.schemas import DriftForecast, GeoJSONFeature

def run_forward_drift_forecast(
    spill_geojson: Dict[str, Any],
    forecast_horizon_hours: int = 24,
    time_step_mins: float = 30.0,
    particle_count: int = 300,
    forcing: EnvironmentalForcing = None
) -> DriftForecast:
    """
    Simulates forward Lagrangian drift corridor for the next 24-48 hours.
    Used for GIS vulnerability intersection and response asset deployment.
    """
    if forcing is None:
        forcing = EnvironmentalForcing()
        
    coords = spill_geojson["coordinates"][0] if spill_geojson["type"] == "Polygon" else spill_geojson["coordinates"][0][0]
    lons = [c[0] for c in coords]
    lats = [c[1] for c in coords]
    minx, maxx = min(lons), max(lons)
    miny, maxy = min(lats), max(lats)
    
    np.random.seed(101)
    p_lon = np.random.uniform(minx, maxx, particle_count)
    p_lat = np.random.uniform(miny, maxy, particle_count)
    
    dt_sec = time_step_mins * 60.0
    steps = int((forecast_horizon_hours * 60) / time_step_mins)
    
    wind_drift_factor = 0.03
    coriolis_angle_rad = math.radians(15.0)
    cos_c = math.cos(coriolis_angle_rad)
    sin_c = math.sin(coriolis_angle_rad)
    diffusion_coef = 2.0
    
    path_samples = [[ [round(p_lon[i], 5), round(p_lat[i], 5)] ] for i in range(0, min(particle_count, 30))]
    
    for step in range(steps):
        t_offset = (step * time_step_mins) / 60.0
        
        u_tot = np.zeros_like(p_lat)
        v_tot = np.zeros_like(p_lat)
        
        for i in range(len(p_lat)):
            u_w, v_w, u_c, v_c = forcing.get_forcing_at(p_lat[i], p_lon[i], t_offset)
            u_w_rot = u_w * cos_c - v_w * sin_c
            v_w_rot = u_w * sin_c + v_w * cos_c
            u_tot[i] = u_c + wind_drift_factor * u_w_rot
            v_tot[i] = v_c + wind_drift_factor * v_w_rot
            
        dx_meters = u_tot * dt_sec + np.random.normal(0, math.sqrt(2 * diffusion_coef * dt_sec), len(p_lat))
        dy_meters = v_tot * dt_sec + np.random.normal(0, math.sqrt(2 * diffusion_coef * dt_sec), len(p_lat))
        
        lat_rad = np.radians(p_lat)
        p_lat += dy_meters / 111000.0
        p_lon += dx_meters / (111000.0 * np.cos(lat_rad))
        
        if step % 4 == 0:
            for idx, p_idx in enumerate(range(0, min(particle_count, 30))):
                path_samples[idx].append([round(p_lon[p_idx], 5), round(p_lat[p_idx], 5)])

    all_lats = p_lat
    all_lons = p_lon
    c_min_lat, c_max_lat = float(np.min(all_lats)), float(np.max(all_lats))
    c_min_lon, c_max_lon = float(np.min(all_lons)), float(np.max(all_lons))
    
    pad_lat = (c_max_lat - c_min_lat) * 0.15 + 0.01
    pad_lon = (c_max_lon - c_min_lon) * 0.15 + 0.01
    
    corridor_coords = [
        [c_min_lon - pad_lon, c_min_lat - pad_lat],
        [c_max_lon + pad_lon, c_min_lat - pad_lat],
        [c_max_lon + pad_lon, c_max_lat + pad_lat],
        [c_min_lon - pad_lon, c_max_lat + pad_lat],
        [c_min_lon - pad_lon, c_min_lat - pad_lat]
    ]
    
    corridor_polygon = GeoJSONFeature(
        geometry={
            "type": "Polygon",
            "coordinates": [corridor_coords]
        },
        properties={
            "horizon_hours": forecast_horizon_hours,
            "description": f"Predicted {forecast_horizon_hours}-Hour Dispersion Corridor"
        }
    )

    return DriftForecast(
        spill_id="spill_001",
        forecast_horizon_hours=forecast_horizon_hours,
        corridor_polygon=corridor_polygon,
        particle_paths=path_samples
    )
