"""
AEGIS-SPILL: AIS Vessel Surveillance & Attribution REST API
Endpoints for:
- Spatial corridor AIS vessel queries
- Raw NMEA 0183 / CSV / JSON AIS log uploads
- Multi-vessel feasibility evaluation against reverse-Lagrangian origin fields
"""

import json
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException, UploadFile, File, Query, Body

from app.models.schemas import (
    AISTrack, FeasibilityResult, OriginProbabilityField, CandidateEvidence
)
from app.modules.ais.ais_feed import ais_feed_service
from app.modules.ais.ais_parser import parse_nmea_log, parse_csv_ais_log, parse_json_ais_feed
from app.modules.ais.feasibility_engine import evaluate_vessel_feasibility
from app.modules.environment.live_metocean import metocean_service
from app.api.cases import CASES_DB

router = APIRouter(prefix="/ais", tags=["ais"])


@router.get("/metocean")
def get_metocean_vectors(
    lat: float = Query(..., description="Latitude of observation"),
    lon: float = Query(..., description="Longitude of observation")
):
    """
    Returns live ocean surface current and 10m wind vectors for the specified location.
    """
    return metocean_service.get_forcing_vectors(lat, lon)



@router.get("/tracks", response_model=List[Dict[str, Any]])
def get_vessel_tracks(
    bbox: str = Query(..., description="min_lon,min_lat,max_lon,max_lat bounding box"),
    lookback_hours: float = Query(24.0, description="Hours of trajectory history to retrieve"),
    case_id: Optional[str] = Query(None, description="Optional case ID to filter candidate feasibility")
):
    """
    Retrieves vessel trajectories within the maritime AOI bounding box.
    If case_id is provided, also computes instant physical feasibility metrics for each vessel.
    """
    try:
        parts = [float(x.strip()) for x in bbox.split(",")]
        if len(parts) != 4:
            raise ValueError("Bounding box must contain exactly 4 comma-separated coordinates: min_lon,min_lat,max_lon,max_lat")
        min_lon, min_lat, max_lon, max_lat = parts
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid bounding box format: {str(e)}")

    tracks = ais_feed_service.get_vessels_in_bbox(
        min_lon, min_lat, max_lon, max_lat,
        reference_time=datetime.now(timezone.utc),
        lookback_hours=lookback_hours
    )

    origin_field = None
    if case_id and case_id in CASES_DB:
        origin_field = CASES_DB[case_id].origin_field

    results = []
    for t in tracks:
        track_dict = t.model_dump()
        if origin_field:
            feasibility = evaluate_vessel_feasibility(t, origin_field)
            track_dict["feasibility"] = feasibility.model_dump()
        results.append(track_dict)

    return results


@router.post("/upload")
async def upload_ais_file(
    file: UploadFile = File(...),
    format_type: str = Query("auto", description="Format: auto, nmea, csv, json")
):
    """
    Uploads custom raw AIS log file (NMEA 0183 !AIVDM, CSV, or JSON).
    Parses and registers trajectories into the surveillance feed.
    """
    try:
        content_bytes = await file.read()
        content_str = content_bytes.decode("utf-8", errors="ignore")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to read file: {str(e)}")

    filename = file.filename.lower()
    parsed_tracks: List[AISTrack] = []

    if format_type == "nmea" or filename.endswith(".nmea") or filename.endswith(".txt") and "!aivdm" in content_str.lower():
        parsed_tracks = parse_nmea_log(content_str)
    elif format_type == "csv" or filename.endswith(".csv"):
        parsed_tracks = parse_csv_ais_log(content_str)
    elif format_type == "json" or filename.endswith(".json"):
        parsed_tracks = parse_json_ais_feed(content_str)
    else:
        # Auto-detect format
        if "!aivdm" in content_str.lower() or "!aivdo" in content_str.lower():
            parsed_tracks = parse_nmea_log(content_str)
        elif content_str.strip().startswith("{") or content_str.strip().startswith("["):
            parsed_tracks = parse_json_ais_feed(content_str)
        else:
            parsed_tracks = parse_csv_ais_log(content_str)

    if not parsed_tracks:
        raise HTTPException(
            status_code=422,
            detail="No valid AIS vessel positions could be parsed from the uploaded file."
        )

    registered_count = ais_feed_service.register_custom_tracks(parsed_tracks)

    return {
        "status": "SUCCESS",
        "filename": file.filename,
        "vessels_parsed": len(parsed_tracks),
        "registered_tracks": registered_count,
        "sample_vessels": [
            {
                "mmsi": t.mmsi,
                "vessel_name": t.vessel_name,
                "points_count": len(t.points),
                "has_gap": t.has_gap
            }
            for t in parsed_tracks[:5]
        ]
    }


@router.post("/evaluate-candidates")
def evaluate_candidates(
    case_id: str = Query(..., description="Active case ID to evaluate against"),
    tracks: Optional[List[AISTrack]] = Body(None, description="Optional custom list of tracks")
):
    """
    Evaluates candidate vessels against the case's reverse-Lagrangian origin probability zone.
    Returns ranked feasibility and attribution breakdown.
    """
    if case_id not in CASES_DB:
        raise HTTPException(status_code=404, detail=f"Case {case_id} not found.")

    case = CASES_DB[case_id]
    origin_field = case.origin_field
    if not origin_field:
        raise HTTPException(status_code=400, detail="Case has no origin probability field computed.")

    eval_tracks = tracks if tracks else case.ais_tracks
    results = []
    
    for t in eval_tracks:
        feas = evaluate_vessel_feasibility(t, origin_field)
        results.append({
            "mmsi": t.mmsi,
            "vessel_name": t.vessel_name,
            "vessel_type": t.vessel_type,
            "flag": t.flag,
            "is_feasible": feas.is_feasible,
            "min_distance_to_origin_km": feas.min_distance_to_origin_km,
            "required_speed_knots": feas.required_speed_knots,
            "max_observed_speed_knots": feas.max_observed_speed_knots,
            "has_gap": t.has_gap,
            "rejection_reasons": feas.rejection_reasons
        })

    # Sort so feasible candidates with smallest distance to origin come first
    results.sort(key=lambda x: (not x["is_feasible"], x["min_distance_to_origin_km"]))

    return {
        "case_id": case_id,
        "total_evaluated": len(results),
        "feasible_count": sum(1 for r in results if r["is_feasible"]),
        "candidates": results
    }
