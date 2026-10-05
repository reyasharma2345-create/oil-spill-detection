import re
from datetime import datetime, timezone
import math
import numpy as np
from typing import List, Dict, Any, Optional
from app.models.schemas import (
    AISTrack, SpillFingerprint, CounterfactualSimulation,
    SimulationMatchMetrics, GeoJSONFeature
)
from app.modules.environment.forcing_grid import EnvironmentalForcing

def run_counterfactual_simulation(
    vessel_track: AISTrack,
    observed_fingerprint: SpillFingerprint,
    observation_lat: float,
    observation_lon: float,
    release_hours_ago: float = 18.0,
    forcing: EnvironmentalForcing = None,
    observation_time_str: Optional[str] = None
) -> CounterfactualSimulation:
    """
    Phase 15: Counterfactual Forward Simulation.
    1. Selects the most plausible release point along the candidate's historical trajectory.
    2. Releases a virtual particle cloud at candidate position at candidate timestamp (t_release).
    3. Forward-simulates physical transport (currents + windage + weathering spreading) to observation timestamp (t_obs).
    4. Constructs the simulated slick polygon and compares its fingerprint against observed slick.
    """
    if forcing is None:
        forcing = EnvironmentalForcing()
        
    orig_lat = observed_fingerprint.centroid_lat
    orig_lon = observed_fingerprint.centroid_lon
    
    best_pt = vessel_track.points[0]
    min_dist = 99999.0
    for pt in vessel_track.points:
        d = math.hypot(pt.lat - orig_lat, pt.lon - orig_lon)
        if d < min_dist:
            min_dist = d
            best_pt = pt
            
    release_lat = best_pt.lat
    release_lon = best_pt.lon
    
    # Derive drift duration to observation time
    drift_hours = release_hours_ago
    m_rel = re.match(r"^T-(\d+(?:\.\d+)?)h?$", best_pt.timestamp.strip(), re.IGNORECASE)
    if m_rel:
        drift_hours = float(m_rel.group(1))
    elif observation_time_str:
        try:
            pt_clean = best_pt.timestamp.strip().replace(" UTC", "").replace("Z", "+00:00")
            obs_clean = observation_time_str.strip().replace(" UTC", "").replace("Z", "+00:00")
            pt_dt = datetime.fromisoformat(pt_clean)
            obs_dt = datetime.fromisoformat(obs_clean)
            diff = (obs_dt - pt_dt).total_seconds() / 3600.0
            if diff > 0.5:
                drift_hours = diff
        except Exception:
            pass

    # Forward Lagrangian Simulation
    num_particles = 300
    dt_sec = 1800.0
    steps = max(2, int((drift_hours * 3600.0) / dt_sec))
    
    heading_rad = math.radians((90 - best_pt.heading_deg) % 360)
    dx_trail = math.cos(heading_rad) * 0.005
    dy_trail = math.sin(heading_rad) * 0.005
    
    np.random.seed(int(hash(vessel_track.mmsi) % 100000))
    t_vals = np.random.uniform(0, 1, num_particles)
    
    p_lats = release_lat + dy_trail * t_vals + np.random.normal(0, 0.002, num_particles)
    p_lons = release_lon + dx_trail * t_vals + np.random.normal(0, 0.002, num_particles)
    
    wind_drift_factor = 0.03
    coriolis_angle_rad = math.radians(15.0)
    cos_c = math.cos(coriolis_angle_rad)
    sin_c = math.sin(coriolis_angle_rad)
    diffusion_coef = 1.8
    
    for step in range(steps):
        t_offset = -(release_hours_ago - (step * 0.5))
        u_tot = np.zeros_like(p_lats)
        v_tot = np.zeros_like(p_lats)
        
        for i in range(len(p_lats)):
            u_w, v_w, u_c, v_c = forcing.get_forcing_at(p_lats[i], p_lons[i], t_offset)
            u_w_rot = u_w * cos_c - v_w * sin_c
            v_w_rot = u_w * sin_c + v_w * cos_c
            u_tot[i] = u_c + wind_drift_factor * u_w_rot
            v_tot[i] = v_c + wind_drift_factor * v_w_rot
            
        dx_meters = u_tot * dt_sec + np.random.normal(0, math.sqrt(2 * diffusion_coef * dt_sec), num_particles)
        dy_meters = v_tot * dt_sec + np.random.normal(0, math.sqrt(2 * diffusion_coef * dt_sec), num_particles)
        
        lat_rad = np.radians(p_lats)
        p_lats += dy_meters / 111000.0
        p_lons += dx_meters / (111000.0 * np.cos(lat_rad))

    sim_centroid_lat = float(np.mean(p_lats))
    sim_centroid_lon = float(np.mean(p_lons))
    
    lat_rad = math.radians(orig_lat)
    dy_km = (sim_centroid_lat - orig_lat) * 111.0
    dx_km = (sim_centroid_lon - orig_lon) * (111.0 * math.cos(lat_rad))
    centroid_error_km = math.hypot(dx_km, dy_km)
    
    sim_min_lat, sim_max_lat = float(np.min(p_lats)), float(np.max(p_lats))
    sim_min_lon, sim_max_lon = float(np.min(p_lons)), float(np.max(p_lons))
    
    sim_coords = [
        [sim_min_lon, sim_min_lat],
        [sim_max_lon, sim_min_lat + (sim_max_lat - sim_min_lat)*0.3],
        [sim_max_lon, sim_max_lat],
        [sim_min_lon + (sim_max_lon - sim_min_lon)*0.4, sim_max_lat],
        [sim_min_lon, sim_min_lat]
    ]
    
    sim_footprint = GeoJSONFeature(
        geometry={
            "type": "Polygon",
            "coordinates": [sim_coords]
        },
        properties={
            "mmsi": vessel_track.mmsi,
            "vessel_name": vessel_track.vessel_name,
            "simulation_type": "Counterfactual Forward Drift"
        }
    )
    
    # Calculate geometric metrics
    # Intersection over Union approximation based on centroid distance and overlap
    iou_score = max(0.0, round(1.0 - (centroid_error_km / 25.0), 3)) if centroid_error_km < 25.0 else 0.0
    boundary_hausdorff_km = round(centroid_error_km * 0.85 + 0.5, 2)
    orientation_delta_deg = round(abs(observed_fingerprint.orientation_deg - best_pt.heading_deg) % 90.0, 1)
    
    sim_area_km2 = (sim_max_lat - sim_min_lat) * 111.0 * (sim_max_lon - sim_min_lon) * 111.0 * math.cos(lat_rad) * 0.7
    area_ratio = round(sim_area_km2 / max(observed_fingerprint.area_km2, 0.1), 2)
    
    centroid_score = max(0.0, 100.0 - (centroid_error_km * 4.0))
    iou_component = iou_score * 100.0
    orientation_score = max(0.0, 100.0 - (orientation_delta_deg * 1.0))
    area_score = max(0.0, 100.0 - abs(1.0 - area_ratio) * 50.0)
    
    similarity_score = round(
        0.45 * centroid_score + 0.25 * iou_component + 0.15 * orientation_score + 0.15 * area_score, 1
    )

    metrics = SimulationMatchMetrics(
        centroid_error_km=round(centroid_error_km, 2),
        iou_score=round(iou_score, 3),
        boundary_hausdorff_km=boundary_hausdorff_km,
        orientation_delta_deg=orientation_delta_deg,
        area_ratio=area_ratio,
        similarity_score=similarity_score
    )

    particle_sample = [[round(p_lons[i], 5), round(p_lats[i], 5)] for i in range(0, num_particles, 5)]

    return CounterfactualSimulation(
        simulation_id=f"sim_{vessel_track.mmsi}",
        mmsi=vessel_track.mmsi,
        vessel_name=vessel_track.vessel_name,
        hypothetical_release_time=best_pt.timestamp if best_pt.timestamp else f"T-{int(drift_hours)}h",
        hypothetical_release_lat=round(release_lat, 5),
        hypothetical_release_lon=round(release_lon, 5),
        simulated_footprint=sim_footprint,
        matching_metrics=metrics,
        particles=particle_sample
    )
