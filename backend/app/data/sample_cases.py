from typing import Dict, List
from app.models.schemas import (
    SpillCase, GeoJSONFeature, SpillFingerprint, DetectionConfirmation,
    OriginProbabilityField, AISTrack, AISPoint, CandidateEvidence,
    ConflictAlert, DriftForecast, VulnerableAsset, ResponseAction
)
from app.modules.fingerprint.fingerprint_engine import analyze_spill_fingerprint
from app.modules.environment.forcing_grid import EnvironmentalForcing
from app.modules.backtrack.lagrangian_hindcast import run_reverse_lagrangian_hindcast
from app.modules.ais.feasibility_engine import evaluate_vessel_feasibility
from app.modules.counterfactual.simulator import run_counterfactual_simulation
from app.modules.scoring.explainable_scorer import evaluate_evidence_and_rank
from app.modules.forecast.drift_forecast import run_forward_drift_forecast
from app.modules.risk.vulnerability_engine import assess_vulnerability_and_recommend
from app.modules.detection.multi_model_qc import evaluate_multi_model_qc

def build_case_gom_01() -> SpillCase:
    """Case 1: Gulf of Mexico - Crude Tanker Secret Discharge"""
    center_lat = 28.6500
    center_lon = -89.4200
    
    # Observed Spill Polygon (Elongated slick aligned with historical south-southeast drift)
    spill_coords = [
        [center_lon - 0.045, center_lat - 0.015],
        [center_lon - 0.015, center_lat - 0.008],
        [center_lon + 0.035, center_lat + 0.012],
        [center_lon + 0.048, center_lat + 0.018],
        [center_lon + 0.042, center_lat + 0.024],
        [center_lon + 0.010, center_lat + 0.016],
        [center_lon - 0.025, center_lat + 0.005],
        [center_lon - 0.050, center_lat - 0.005],
        [center_lon - 0.045, center_lat - 0.015]
    ]
    
    spill_poly_feature = GeoJSONFeature(
        geometry={"type": "Polygon", "coordinates": [spill_coords]},
        properties={"spill_id": "SPILL-GOM-2024-001", "confidence": 0.94, "sensor": "Sentinel-1B C-SAR"}
    )
    
    fingerprint = analyze_spill_fingerprint("SPILL-GOM-2024-001", spill_poly_feature.geometry.model_dump())
    
    confirmation = DetectionConfirmation(
        spill_id="SPILL-GOM-2024-001",
        sar_probability=0.96,
        optical_probability=0.88,
        tir_confidence=0.74,
        temporal_consistency=0.92,
        classification="OIL",
        overall_confidence=0.94,
        quality_notes=[
            "High contrast SAR low-backscatter anomaly (-22 dB)",
            "Sentinel-2 MSI corroboration: dampening of capillary waves detected",
            "Thermal infrared shows mild negative contrast (-0.8 K) consistent with evaporative cooling"
        ]
    )
    
    forcing = EnvironmentalForcing(mean_wind_speed_ms=7.8, wind_dir_deg=220.0,
                                   mean_current_speed_ms=0.38, current_dir_deg=205.0)
    
    origin_field = run_reverse_lagrangian_hindcast(
        spill_geojson=spill_poly_feature.geometry.model_dump(),
        observation_time_str="2024-04-18T05:32:00Z",
        max_hindcast_hours=18.0,
        forcing=forcing
    )
    
    # Candidate Vessels in AOI during release window
    # Candidate 1: MT Starlight Spirit (Crude Oil Tanker) - TRUE SOURCE
    track_1 = AISTrack(
        mmsi="368945000",
        vessel_name="MT Starlight Spirit",
        vessel_type="Crude Oil Tanker",
        flag="Panama",
        imo="9481234",
        points=[
            AISPoint(mmsi="368945000", timestamp="T-22h", lat=origin_field.probable_origin_lat - 0.12, lon=origin_field.probable_origin_lon - 0.10, speed_knots=12.4, heading_deg=42.0),
            AISPoint(mmsi="368945000", timestamp="T-18h", lat=origin_field.probable_origin_lat - 0.02, lon=origin_field.probable_origin_lon - 0.01, speed_knots=11.8, heading_deg=45.0),
            AISPoint(mmsi="368945000", timestamp="T-14h", lat=origin_field.probable_origin_lat + 0.09, lon=origin_field.probable_origin_lon + 0.08, speed_knots=12.6, heading_deg=44.0),
            AISPoint(mmsi="368945000", timestamp="T-10h", lat=origin_field.probable_origin_lat + 0.21, lon=origin_field.probable_origin_lon + 0.18, speed_knots=13.1, heading_deg=43.0),
        ],
        has_gap=False
    )
    
    # Candidate 2: MV Pacific Pioneer (Bulk Carrier) - IMPOSSIBLE CANDIDATE (Too far)
    track_2 = AISTrack(
        mmsi="413876000",
        vessel_name="MV Pacific Pioneer",
        vessel_type="Bulk Carrier",
        flag="Liberia",
        imo="9612988",
        points=[
            AISPoint(mmsi="413876000", timestamp="T-20h", lat=origin_field.probable_origin_lat + 0.45, lon=origin_field.probable_origin_lon - 0.50, speed_knots=10.2, heading_deg=110.0),
            AISPoint(mmsi="413876000", timestamp="T-16h", lat=origin_field.probable_origin_lat + 0.40, lon=origin_field.probable_origin_lon - 0.35, speed_knots=10.5, heading_deg=112.0),
            AISPoint(mmsi="413876000", timestamp="T-12h", lat=origin_field.probable_origin_lat + 0.36, lon=origin_field.probable_origin_lon - 0.20, speed_knots=10.1, heading_deg=111.0),
        ],
        has_gap=False
    )
    
    # Candidate 3: MT Baltic Pearl (Chemical / Oil Products Tanker) - MODERATE SIMILARITY
    track_3 = AISTrack(
        mmsi="257891000",
        vessel_name="MT Baltic Pearl",
        vessel_type="Chemical Tanker",
        flag="Norway",
        imo="9356611",
        points=[
            AISPoint(mmsi="257891000", timestamp="T-21h", lat=origin_field.probable_origin_lat + 0.15, lon=origin_field.probable_origin_lon - 0.15, speed_knots=14.0, heading_deg=160.0),
            AISPoint(mmsi="257891000", timestamp="T-17h", lat=origin_field.probable_origin_lat + 0.05, lon=origin_field.probable_origin_lon - 0.08, speed_knots=13.8, heading_deg=158.0),
            AISPoint(mmsi="257891000", timestamp="T-13h", lat=origin_field.probable_origin_lat - 0.08, lon=origin_field.probable_origin_lon - 0.02, speed_knots=14.2, heading_deg=162.0),
        ],
        has_gap=False
    )
    
    # Candidate 4: CS Global Voyager (Container Ship) - HAS AIS GAP
    track_4 = AISTrack(
        mmsi="563912000",
        vessel_name="CS Global Voyager",
        vessel_type="Container Ship",
        flag="Singapore",
        imo="9721099",
        points=[
            AISPoint(mmsi="563912000", timestamp="T-24h", lat=origin_field.probable_origin_lat - 0.25, lon=origin_field.probable_origin_lon + 0.15, speed_knots=19.5, heading_deg=310.0),
            AISPoint(mmsi="563912000", timestamp="T-12h", lat=origin_field.probable_origin_lat + 0.10, lon=origin_field.probable_origin_lon - 0.18, speed_knots=18.0, heading_deg=315.0),
        ],
        has_gap=True,
        gap_details="Unexplained 6.5h AIS transmission gap while traversing high-risk origin quadrant."
    )
    
    vessel_tracks = [track_1, track_2, track_3, track_4]
    
    # Evaluate candidates
    candidate_evidences: List[CandidateEvidence] = []
    effective_drift_h = origin_field.estimated_drift_duration_hours or 18.0
    for trk in vessel_tracks:
        feasibility = evaluate_vessel_feasibility(trk, origin_field)
        sim = run_counterfactual_simulation(
            vessel_track=trk,
            observed_fingerprint=fingerprint,
            observation_lat=center_lat,
            observation_lon=center_lon,
            release_hours_ago=effective_drift_h,
            forcing=forcing,
            observation_time_str="2024-04-18T05:32:00 UTC"
        )
        cand_ev = evaluate_evidence_and_rank(trk, feasibility, sim, confirmation)
        candidate_evidences.append(cand_ev)
        
    # Sort candidates by final score descending
    candidate_evidences.sort(key=lambda c: c.final_score, reverse=True)
    for idx, cand in enumerate(candidate_evidences):
        cand.rank = idx + 1
        
    forecast = run_forward_drift_forecast(
        spill_geojson=spill_poly_feature.geometry.model_dump(),
        forecast_horizon_hours=24,
        forcing=forcing
    )
    
    vulnerable_assets, response_actions = assess_vulnerability_and_recommend(
        forecast=forecast,
        case_region="Gulf of Mexico",
        reference_lat=center_lat,
        reference_lon=center_lon
    )
    
    return SpillCase(
        case_id="GOM-2024-0418",
        title="Mississippi Canyon / Barataria Drift Slick",
        region="Gulf of Mexico (Offshore Louisiana)",
        aoi_bounds=[center_lon - 0.6, center_lat - 0.5, center_lon + 0.6, center_lat + 0.5],
        observation_time="2024-04-18T05:32:00 UTC",
        sensor="Sentinel-1 SAR (C-Band VV)",
        status="COMPLETED",
        spill_polygon=spill_poly_feature,
        fingerprint=fingerprint,
        confirmation=confirmation,
        origin_field=origin_field,
        ais_tracks=vessel_tracks,
        candidates=candidate_evidences,
        forecast=forecast,
        vulnerable_assets=vulnerable_assets,
        response_actions=response_actions,
        created_at="2024-04-18T06:15:00 UTC"
    )

def build_case_mumbai_02() -> SpillCase:
    """Case 2: Mumbai Offshore / Arabian Sea - ONGC High Corridor Release"""
    center_lat = 18.9800
    center_lon = 72.4500
    
    spill_coords = [
        [center_lon - 0.038, center_lat - 0.020],
        [center_lon - 0.010, center_lat - 0.012],
        [center_lon + 0.025, center_lat + 0.010],
        [center_lon + 0.040, center_lat + 0.022],
        [center_lon + 0.032, center_lat + 0.028],
        [center_lon + 0.005, center_lat + 0.018],
        [center_lon - 0.020, center_lat + 0.005],
        [center_lon - 0.042, center_lat - 0.010],
        [center_lon - 0.038, center_lat - 0.020]
    ]
    
    spill_poly_feature = GeoJSONFeature(
        geometry={"type": "Polygon", "coordinates": [spill_coords]},
        properties={"spill_id": "SPILL-BOM-2024-002", "confidence": 0.91, "sensor": "Sentinel-1A IW"}
    )
    
    fingerprint = analyze_spill_fingerprint("SPILL-BOM-2024-002", spill_poly_feature.geometry.model_dump())
    
    confirmation = evaluate_multi_model_qc(
        spill_id="SPILL-BOM-2024-002",
        sar_probability=0.92,
        optical_probability=None,
        tir_confidence=None,
        temporal_consistency=0.89,
        fingerprint=fingerprint
    )
    
    forcing = EnvironmentalForcing(mean_wind_speed_ms=6.5, wind_dir_deg=250.0,
                                   mean_current_speed_ms=0.42, current_dir_deg=235.0)
    
    origin_field = run_reverse_lagrangian_hindcast(
        spill_geojson=spill_poly_feature.geometry.model_dump(),
        observation_time_str="2024-05-12T12:18:00Z",
        max_hindcast_hours=16.0,
        forcing=forcing
    )
    
    track_1 = AISTrack(
        mmsi="419001234",
        vessel_name="MT Samudra Ratna",
        vessel_type="Product Tanker",
        flag="India",
        imo="9523145",
        points=[
            AISPoint(mmsi="419001234", timestamp="T-18h", lat=origin_field.probable_origin_lat - 0.10, lon=origin_field.probable_origin_lon - 0.08, speed_knots=11.5, heading_deg=52.0),
            AISPoint(mmsi="419001234", timestamp="T-14h", lat=origin_field.probable_origin_lat - 0.01, lon=origin_field.probable_origin_lon - 0.01, speed_knots=11.2, heading_deg=50.0),
            AISPoint(mmsi="419001234", timestamp="T-10h", lat=origin_field.probable_origin_lat + 0.08, lon=origin_field.probable_origin_lon + 0.07, speed_knots=11.7, heading_deg=51.0),
        ],
        has_gap=False
    )
    
    track_2 = AISTrack(
        mmsi="355789000",
        vessel_name="OSV Sagar Kanya",
        vessel_type="Offshore Supply Ship",
        flag="Panama",
        imo="9341122",
        points=[
            AISPoint(mmsi="355789000", timestamp="T-16h", lat=origin_field.probable_origin_lat + 0.06, lon=origin_field.probable_origin_lon - 0.12, speed_knots=8.5, heading_deg=140.0),
            AISPoint(mmsi="355789000", timestamp="T-12h", lat=origin_field.probable_origin_lat - 0.04, lon=origin_field.probable_origin_lon - 0.05, speed_knots=8.2, heading_deg=142.0),
        ],
        has_gap=False
    )
    
    vessel_tracks = [track_1, track_2]
    candidate_evidences = []
    effective_drift_bom = origin_field.estimated_drift_duration_hours or 16.0
    for trk in vessel_tracks:
        feasibility = evaluate_vessel_feasibility(trk, origin_field)
        sim = run_counterfactual_simulation(
            vessel_track=trk,
            observed_fingerprint=fingerprint,
            observation_lat=center_lat,
            observation_lon=center_lon,
            release_hours_ago=effective_drift_bom,
            forcing=forcing,
            observation_time_str="2024-05-12T12:18:00 UTC"
        )
        cand_ev = evaluate_evidence_and_rank(trk, feasibility, sim, confirmation)
        candidate_evidences.append(cand_ev)
        
    candidate_evidences.sort(key=lambda c: c.final_score, reverse=True)
    for idx, cand in enumerate(candidate_evidences):
        cand.rank = idx + 1
        
    forecast = run_forward_drift_forecast(spill_poly_feature.geometry.model_dump(), 24, forcing=forcing)
    vulnerable_assets, response_actions = assess_vulnerability_and_recommend(forecast, "Mumbai Coast", center_lat, center_lon)
    
    return SpillCase(
        case_id="MUM-2024-0512",
        title="Mumbai High Offshore Approach Spill",
        region="Arabian Sea (West Coast of India)",
        aoi_bounds=[center_lon - 0.5, center_lat - 0.5, center_lon + 0.5, center_lat + 0.5],
        observation_time="2024-05-12T12:18:00 UTC",
        sensor="Sentinel-1 SAR",
        status="COMPLETED",
        spill_polygon=spill_poly_feature,
        fingerprint=fingerprint,
        confirmation=confirmation,
        origin_field=origin_field,
        ais_tracks=vessel_tracks,
        candidates=candidate_evidences,
        forecast=forecast,
        vulnerable_assets=vulnerable_assets,
        response_actions=response_actions,
        created_at="2024-05-12T13:00:00 UTC"
    )

def get_all_sample_cases() -> Dict[str, SpillCase]:
    c1 = build_case_gom_01()
    c2 = build_case_mumbai_02()
    return {
        c1.case_id: c1,
        c2.case_id: c2
    }
