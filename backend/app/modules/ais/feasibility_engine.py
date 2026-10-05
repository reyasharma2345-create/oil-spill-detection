from datetime import datetime, timezone
import math
import re
from typing import List, Tuple, Dict, Any, Optional
from app.models.schemas import AISTrack, FeasibilityResult, OriginProbabilityField

def haversine_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculates great-circle distance between two points in kilometers."""
    R = 6371.0  # Earth radius in km
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2.0) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2.0) ** 2)
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return R * c


def _parse_time_to_dt(ts_str: str) -> Optional[datetime]:
    """Helper to parse ISO/UTC timestamp strings."""
    if not ts_str:
        return None
    clean = ts_str.strip().replace(" UTC", "").replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(clean)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        pass
    for fmt in ["%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"]:
        try:
            return datetime.strptime(clean[:19], fmt).replace(tzinfo=timezone.utc)
        except Exception:
            continue
    return None


def calculate_temporal_offset_hours(
    point_timestamp: str,
    release_timestamp: Optional[str],
    estimated_drift_hours: float = 18.0
) -> float:
    """
    Computes absolute temporal delta in hours between an AIS point and the estimated release time.
    Supports both ISO 8601 timestamps and relative offsets like 'T-18h'.
    """
    # 1. Relative offset format check: e.g. "T-18h", "T-14.5h"
    m_pt = re.match(r"^T-(\d+(?:\.\d+)?)h?$", point_timestamp.strip(), re.IGNORECASE)
    if m_pt:
        pt_hours_ago = float(m_pt.group(1))
        # release occurred estimated_drift_hours ago
        return abs(pt_hours_ago - estimated_drift_hours)
    
    # 2. ISO / UTC timestamp format
    pt_dt = _parse_time_to_dt(point_timestamp)
    rel_dt = _parse_time_to_dt(release_timestamp) if release_timestamp else None
    
    if pt_dt and rel_dt:
        return abs((pt_dt - rel_dt).total_seconds()) / 3600.0
        
    return 0.0


def evaluate_vessel_feasibility(
    track: AISTrack,
    origin_field: OriginProbabilityField,
    max_allowable_speed_knots: float = 25.0
) -> FeasibilityResult:
    """
    Phase 13: Impossible Vessel Engine.
    Evaluates whether a vessel's trajectory is physically and temporally consistent with the inferred origin region.
    Evaluates:
    1. Spatial proximity to probable origin centroid (envelope < 35 km)
    2. Temporal coincidence with estimated release window
    3. Kinematic intercept speed required to transit from closest reported point to origin
    """
    orig_lat = origin_field.probable_origin_lat
    orig_lon = origin_field.probable_origin_lon
    
    if not track.points:
        return FeasibilityResult(
            mmsi=track.mmsi,
            vessel_name=track.vessel_name,
            is_feasible=False,
            required_speed_knots=99.0,
            max_observed_speed_knots=0.0,
            min_distance_to_origin_km=999.0,
            time_delta_hours=24.0,
            temporal_offset_hours=24.0,
            rejection_reasons=["No AIS trajectory points available in surveillance AOI."]
        )

    # 1. Find point of closest approach (PCA) to origin
    min_dist = 999999.0
    pca_point = track.points[0]
    max_observed_speed = 0.0
    
    est_drift_h = origin_field.estimated_drift_duration_hours or 18.0
    rel_ts = origin_field.estimated_release_timestamp or origin_field.peak_release_time
    
    for pt in track.points:
        dist = haversine_distance_km(pt.lat, pt.lon, orig_lat, orig_lon)
        if dist < min_dist:
            min_dist = dist
            pca_point = pt
        if pt.speed_knots > max_observed_speed:
            max_observed_speed = pt.speed_knots
            
    # Calculate temporal alignment between PCA point and inferred release time
    temporal_offset_h = calculate_temporal_offset_hours(
        pca_point.timestamp, rel_ts, est_drift_h
    )

    # 2. Check physical & temporal feasibility
    rejection_reasons = []
    is_feasible = True
    
    # Threshold A: Spatial proximity envelope (35 km)
    PROXIMITY_THRESHOLD_KM = 35.0
    if min_dist > PROXIMITY_THRESHOLD_KM:
        is_feasible = False
        rejection_reasons.append(
            f"Closest approach ({min_dist:.1f} km at {pca_point.timestamp}) exceeds maximum dispersion envelope ({PROXIMITY_THRESHOLD_KM} km)."
        )
        
    # Threshold B: Temporal window consistency
    # Tolerance allows passage within release window plus 3.5h margin
    TEMPORAL_WINDOW_TOLERANCE_HOURS = 4.5
    if temporal_offset_h > TEMPORAL_WINDOW_TOLERANCE_HOURS:
        is_feasible = False
        win_disp = origin_field.release_window_display or f"{origin_field.release_window_start} to {origin_field.release_window_end}"
        rejection_reasons.append(
            f"Temporal mismatch: Closest passage at {pca_point.timestamp} is {temporal_offset_h:.1f}h outside estimated release window ({win_disp})."
        )
        
    # Threshold C: Required intercept speed
    effective_time_delta = max(temporal_offset_h, 1.0)
    required_speed_knots = (min_dist / 1.852) / effective_time_delta
    
    if required_speed_knots > max_allowable_speed_knots:
        is_feasible = False
        rejection_reasons.append(
            f"Required speed to reach origin ({required_speed_knots:.1f} kts) exceeds vessel physical limit ({max_allowable_speed_knots} kts)."
        )
        
    if track.has_gap:
        rejection_reasons.append(
            f"Forensic note: {track.gap_details or 'Unexplained AIS transmission gap detected during transit.'}"
        )

    return FeasibilityResult(
        mmsi=track.mmsi,
        vessel_name=track.vessel_name,
        is_feasible=is_feasible,
        required_speed_knots=round(required_speed_knots, 1),
        max_observed_speed_knots=round(max_observed_speed, 1),
        min_distance_to_origin_km=round(min_dist, 2),
        time_delta_hours=round(effective_time_delta, 1),
        closest_passage_time=pca_point.timestamp,
        closest_passage_coords=[round(pca_point.lat, 5), round(pca_point.lon, 5)],
        temporal_offset_hours=round(temporal_offset_h, 1),
        rejection_reasons=rejection_reasons
    )
