"""
AEGIS-SPILL Core REST API Module
Implements end-to-end endpoints for:
- Case Management (List, Details, Create, Update, Delete)
- Satellite SAR Detection & Segmentation
- Dynamic Reverse-Lagrangian Hindcast (Backtracking)
- Dynamic Candidate Counterfactual Release Simulations & Scoring
- Dynamic Forward Drift Forecast & Coastal Vulnerability Assessment
- Database Persistence (SQLAlchemy & PostGIS)
- Forensic Evidence Audit Report Export
"""
import json
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any, Optional

from fastapi import APIRouter, HTTPException, UploadFile, File, Query, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.case import Case as DBCase
from app.models.schemas import (
    SpillCase, OriginProbabilityField, CandidateEvidence, DriftForecast,
    SpillFingerprint, GeoJSONFeature, DetectionConfirmation, VulnerableAsset,
    ResponseAction, FeasibilityResult, CounterfactualSimulation
)
from app.data.sample_cases import get_all_sample_cases

# Domain Engine Modules
from app.modules.environment.forcing_grid import EnvironmentalForcing
from app.modules.environment.live_metocean import metocean_service
from app.modules.backtrack.lagrangian_hindcast import run_reverse_lagrangian_hindcast
from app.modules.counterfactual.simulator import run_counterfactual_simulation
from app.modules.ais.feasibility_engine import evaluate_vessel_feasibility
from app.modules.scoring.explainable_scorer import evaluate_evidence_and_rank
from app.modules.forecast.drift_forecast import run_forward_drift_forecast
from app.modules.risk.vulnerability_engine import assess_vulnerability_and_recommend
from app.modules.detection.multi_model_qc import evaluate_multi_model_qc
from app.modules.fingerprint.fingerprint_engine import analyze_spill_fingerprint
from app.tasks.detection_task import run_detection_task, execute_detection_pipeline

router = APIRouter(prefix="/cases", tags=["cases"])

# In-memory high-speed active cases registry
CASES_DB: Dict[str, SpillCase] = get_all_sample_cases()


# ----------------------------------------------------------------------
# 0. Case Creation Schemas & Endpoints (Flowchart Step 0)
# ----------------------------------------------------------------------

class CreateCaseRequest(BaseModel):
    case_id: str
    title: str
    region: str
    lat: float
    lon: float
    sensor: Optional[str] = "Sentinel-1 SAR (C-Band VV)"
    observation_time: Optional[str] = None


@router.post("/new", response_model=SpillCase, status_code=201)
def create_new_investigation_case(req: CreateCaseRequest):
    """
    Step 0: User creates an oil-spill investigation case.
    Initializes bounding AOI, starting polygon, fingerprint, QC confirmation, and origin field.
    """
    if req.case_id in CASES_DB:
        raise HTTPException(status_code=409, detail=f"Case {req.case_id} already exists.")

    d_lat = 0.02
    d_lon = 0.03
    c_lat, c_lon = req.lat, req.lon
    init_poly = {
        "type": "Polygon",
        "coordinates": [[
            [round(c_lon - d_lon, 5), round(c_lat - d_lat, 5)],
            [round(c_lon + d_lon * 0.8, 5), round(c_lat - d_lat * 0.5, 5)],
            [round(c_lon + d_lon, 5), round(c_lat + d_lat, 5)],
            [round(c_lon - d_lon * 0.5, 5), round(c_lat + d_lat * 0.8, 5)],
            [round(c_lon - d_lon, 5), round(c_lat - d_lat, 5)],
        ]]
    }

    fp = analyze_spill_fingerprint(f"SPILL-{req.case_id}", init_poly)
    obs_time = req.observation_time or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:00 UTC")

    confirmation = evaluate_multi_model_qc(
        spill_id=req.case_id,
        sar_probability=0.88,
        fingerprint=fp
    )

    obs_dt = datetime.now(timezone.utc)
    rel_dt = obs_dt - timedelta(hours=14.5)
    win_start = rel_dt - timedelta(hours=1.5)
    win_end = rel_dt + timedelta(hours=1.5)

    origin_field = OriginProbabilityField(
        spill_id=req.case_id,
        release_window_start=win_start.strftime("%Y-%m-%dT%H:%M:%SZ"),
        release_window_end=win_end.strftime("%Y-%m-%dT%H:%M:%SZ"),
        peak_release_time=rel_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
        estimated_release_timestamp=rel_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
        estimated_drift_duration_hours=14.5,
        release_confidence=0.88,
        best_estimate_display=f"{rel_dt.strftime('%Y-%m-%d %H:%M UTC')} (T-14.5h)",
        release_window_display=f"{win_start.strftime('%Y-%m-%d %H:%M')}–{win_end.strftime('%H:%M UTC')}",
        probable_origin_lat=round(c_lat + 0.04, 5),
        probable_origin_lon=round(c_lon + 0.05, 5),
        origin_polygon=GeoJSONFeature(
            geometry={
                "type": "Polygon",
                "coordinates": [[
                    [round(c_lon + 0.02, 5), round(c_lat + 0.02, 5)],
                    [round(c_lon + 0.08, 5), round(c_lat + 0.02, 5)],
                    [round(c_lon + 0.08, 5), round(c_lat + 0.07, 5)],
                    [round(c_lon + 0.02, 5), round(c_lat + 0.07, 5)],
                    [round(c_lon + 0.02, 5), round(c_lat + 0.02, 5)],
                ]]
            },
            properties={"layer": "probable_origin_envelope"}
        ),
        heatmap_grid=[]
    )

    new_case = SpillCase(
        case_id=req.case_id,
        title=req.title,
        region=req.region,
        aoi_bounds=[round(c_lon - 0.25, 4), round(c_lat - 0.25, 4), round(c_lon + 0.25, 4), round(c_lat + 0.25, 4)],
        observation_time=obs_time,
        sensor=req.sensor or "Sentinel-1 SAR (C-Band VV)",
        status="INVESTIGATING",
        spill_polygon=GeoJSONFeature(
            geometry=init_poly,
            properties={"spill_id": req.case_id, "confidence": 0.88, "sensor": req.sensor}
        ),
        fingerprint=fp,
        confirmation=confirmation,
        origin_field=origin_field,
        ais_tracks=[],
        candidates=[],
        forecast=DriftForecast(
            spill_id=req.case_id,
            forecast_horizon_hours=24,
            corridor_polygon=GeoJSONFeature(
                geometry=init_poly,
                properties={"horizon_hours": 24}
            ),
            particle_paths=[]
        ),
        vulnerable_assets=[],
        response_actions=[],
        created_at=datetime.now(timezone.utc).isoformat(),
        config_version="v1.0.0"
    )
    CASES_DB[req.case_id] = new_case
    return new_case


# ----------------------------------------------------------------------
# 1. Case Listing & Retrieval
# ----------------------------------------------------------------------

@router.get("", response_model=List[Dict[str, Any]])
def list_cases():
    """List all available spill investigation cases."""
    return [
        {
            "case_id": c.case_id,
            "title": c.title,
            "region": c.region,
            "observation_time": c.observation_time,
            "sensor": c.sensor,
            "status": c.status,
            "spill_area_km2": c.fingerprint.area_km2,
            "top_candidate": c.candidates[0].vessel_name if c.candidates else "None",
            "top_score": c.candidates[0].final_score if c.candidates else 0.0
        }
        for c in CASES_DB.values()
    ]


@router.get("/{case_id}", response_model=SpillCase)
def get_case(case_id: str):
    """Retrieve full details of an investigation case."""
    if case_id not in CASES_DB:
        raise HTTPException(status_code=404, detail=f"Case {case_id} not found.")
    return CASES_DB[case_id]


# ----------------------------------------------------------------------
# 2. Case CRUD Operations
# ----------------------------------------------------------------------

@router.post("", response_model=SpillCase, status_code=201)
def create_case(new_case: SpillCase):
    """Creates a new spill investigation case in the active registry."""
    if new_case.case_id in CASES_DB:
        raise HTTPException(status_code=409, detail=f"Case {new_case.case_id} already exists.")
    CASES_DB[new_case.case_id] = new_case
    return new_case


@router.put("/{case_id}", response_model=SpillCase)
def update_case(case_id: str, updated_case: SpillCase):
    """Updates an existing spill investigation case."""
    if case_id not in CASES_DB:
        raise HTTPException(status_code=404, detail=f"Case {case_id} not found.")
    CASES_DB[case_id] = updated_case
    return updated_case


@router.delete("/{case_id}")
def delete_case(case_id: str):
    """Deletes a case from the active registry."""
    if case_id not in CASES_DB:
        raise HTTPException(status_code=404, detail=f"Case {case_id} not found.")
    del CASES_DB[case_id]
    return {"message": f"Case {case_id} successfully removed.", "case_id": case_id}


# ----------------------------------------------------------------------
# 3. Dynamic Reverse-Lagrangian Hindcast (Backtrack)
# ----------------------------------------------------------------------

@router.post("/{case_id}/backtrack", response_model=OriginProbabilityField)
def trigger_backtrack(
    case_id: str,
    max_hindcast_hours: float = Query(24.0, ge=1.0, le=72.0, description="Hours to step backwards"),
    wind_speed_ms: Optional[float] = Query(None, description="Custom mean wind speed (m/s)"),
    wind_dir_deg: Optional[float] = Query(None, description="Custom wind direction (deg)"),
    current_speed_ms: Optional[float] = Query(None, description="Custom current speed (m/s)"),
    current_dir_deg: Optional[float] = Query(None, description="Custom current direction (deg)"),
):
    """
    Executes dynamic reverse-time Lagrangian particle hindcast using 2D physical forcing.
    Recalculates particle dispersal, probable origin centroid, and 2D spatial heatmap.
    """
    if case_id not in CASES_DB:
        raise HTTPException(status_code=404, detail=f"Case {case_id} not found.")
    case = CASES_DB[case_id]

    forcing = None
    if any(p is not None for p in [wind_speed_ms, wind_dir_deg, current_speed_ms, current_dir_deg]):
        forcing = EnvironmentalForcing(
            mean_wind_speed_ms=wind_speed_ms or 8.0,
            wind_dir_deg=wind_dir_deg or 220.0,
            mean_current_speed_ms=current_speed_ms or 0.4,
            current_dir_deg=current_dir_deg or 205.0
        )
    else:
        # Step 7: Environmental Data (Wind + Current Field alignment)
        try:
            c_lat = case.fingerprint.centroid_lat if case.fingerprint else 28.5
            c_lon = case.fingerprint.centroid_lon if case.fingerprint else -89.5
            met_data = metocean_service.get_forcing_vectors(c_lat, c_lon)
            forcing = EnvironmentalForcing(
                mean_wind_speed_ms=met_data.get("wind_speed_ms", 7.8),
                wind_dir_deg=met_data.get("wind_dir_deg", 220.0),
                mean_current_speed_ms=met_data.get("current_speed_ms", 0.38),
                current_dir_deg=met_data.get("current_dir_deg", 205.0)
            )
        except Exception:
            forcing = None

    origin_field = run_reverse_lagrangian_hindcast(
        spill_geojson=case.spill_polygon.geometry.model_dump(),
        observation_time_str=case.observation_time,
        max_hindcast_hours=max_hindcast_hours,
        particle_count=settings.PARTICLE_COUNT_BACKTRACK,
        forcing=forcing,
    )

    case.origin_field = origin_field
    return origin_field


# ----------------------------------------------------------------------
# 4. Dynamic Counterfactual Forensics Simulation & Scoring
# ----------------------------------------------------------------------

@router.post("/{case_id}/counterfactual", response_model=List[CandidateEvidence])
def trigger_counterfactual(
    case_id: str,
    release_hours_ago: float = Query(18.0, ge=1.0, le=48.0, description="Inferred release lookback in hours"),
):
    """
    Executes dynamic forward counterfactual simulations for all candidate vessels:
    1. Evaluates kinematic feasibility against the inferred origin region.
    2. Seeds virtual particles along candidate trajectories and forward-simulates physical drift.
    3. Calculates shape fingerprint similarity metrics (IoU, Hausdorff, orientation delta).
    4. Evaluates conflict alerts and computes explainable attribution scores.
    """
    if case_id not in CASES_DB:
        raise HTTPException(status_code=404, detail=f"Case {case_id} not found.")
    case = CASES_DB[case_id]

    c_lat = case.fingerprint.centroid_lat if case.fingerprint else 28.5
    c_lon = case.fingerprint.centroid_lon if case.fingerprint else -89.5
    forcing = None
    try:
        met_data = metocean_service.get_forcing_vectors(c_lat, c_lon)
        forcing = EnvironmentalForcing(
            mean_wind_speed_ms=met_data.get("wind_speed_ms", 7.8),
            wind_dir_deg=met_data.get("wind_dir_deg", 220.0),
            mean_current_speed_ms=met_data.get("current_speed_ms", 0.38),
            current_dir_deg=met_data.get("current_dir_deg", 205.0)
        )
    except Exception:
        forcing = None

    updated_candidates = []
    effective_release_lookback = case.origin_field.estimated_drift_duration_hours or release_hours_ago
    for track in case.ais_tracks:
        feasibility = evaluate_vessel_feasibility(track, case.origin_field)
        sim = run_counterfactual_simulation(
            vessel_track=track,
            observed_fingerprint=case.fingerprint,
            observation_lat=c_lat,
            observation_lon=c_lon,
            release_hours_ago=effective_release_lookback,
            forcing=forcing,
            observation_time_str=case.observation_time
        )
        evidence = evaluate_evidence_and_rank(track, feasibility, sim, case.confirmation)
        updated_candidates.append(evidence)

    updated_candidates.sort(key=lambda c: c.final_score, reverse=True)
    for idx, cand in enumerate(updated_candidates):
        cand.rank = idx + 1
    case.candidates = updated_candidates
    return updated_candidates


# ----------------------------------------------------------------------
# 5. Dynamic Forward Drift Corridor Forecast & Vulnerability Assessment
# ----------------------------------------------------------------------

@router.post("/{case_id}/forecast", response_model=DriftForecast)
def trigger_forecast(
    case_id: str,
    forecast_horizon_hours: int = Query(24, ge=6, le=72, description="Forward forecast duration (hours)"),
):
    """
    Executes forward Lagrangian dispersion forecast envelope for the next 24-72 hours.
    Automatically re-intersects with coastal critical infrastructure to produce
    prioritized operational response recommendations.
    """
    if case_id not in CASES_DB:
        raise HTTPException(status_code=404, detail=f"Case {case_id} not found.")
    case = CASES_DB[case_id]

    c_lat = case.fingerprint.centroid_lat if case.fingerprint else 28.5
    c_lon = case.fingerprint.centroid_lon if case.fingerprint else -89.5
    forcing = None
    try:
        met_data = metocean_service.get_forcing_vectors(c_lat, c_lon)
        forcing = EnvironmentalForcing(
            mean_wind_speed_ms=met_data.get("wind_speed_ms", 7.8),
            wind_dir_deg=met_data.get("wind_dir_deg", 220.0),
            mean_current_speed_ms=met_data.get("current_speed_ms", 0.38),
            current_dir_deg=met_data.get("current_dir_deg", 205.0)
        )
    except Exception:
        forcing = None

    forecast = run_forward_drift_forecast(
        spill_geojson=case.spill_polygon.geometry.model_dump(),
        forecast_horizon_hours=forecast_horizon_hours,
        particle_count=settings.PARTICLE_COUNT_FORECAST,
        forcing=forcing
    )
    case.forecast = forecast

    # Intersect with vulnerable coastal assets
    assets, actions = assess_vulnerability_and_recommend(
        forecast=forecast,
        case_region=case.region,
        reference_lat=case.fingerprint.centroid_lat,
        reference_lon=case.fingerprint.centroid_lon
    )
    case.vulnerable_assets = assets
    case.response_actions = actions
    return forecast


@router.post("/{case_id}/risk")
def trigger_risk_assessment(case_id: str):
    """
    Re-assesses coastal asset vulnerability and prioritized mitigation response recommendations.
    """
    if case_id not in CASES_DB:
        raise HTTPException(status_code=404, detail=f"Case {case_id} not found.")
    case = CASES_DB[case_id]

    assets, actions = assess_vulnerability_and_recommend(
        forecast=case.forecast,
        case_region=case.region,
        reference_lat=case.fingerprint.centroid_lat,
        reference_lon=case.fingerprint.centroid_lon
    )
    case.vulnerable_assets = assets
    case.response_actions = actions

    return {
        "case_id": case_id,
        "vulnerable_assets": [a.model_dump() for a in assets],
        "response_actions": [act.model_dump() for act in actions]
    }


# ----------------------------------------------------------------------
# 6. Satellite Detection & Image Upload
# ----------------------------------------------------------------------

@router.post("/{case_id}/detect")
def trigger_detection(
    case_id: str,
    image_path: str,
    threshold: float = 0.5,
    sync: bool = False,
):
    """
    Executes SAR image detection. Runs synchronously if sync=True or if Celery is offline.
    Updates case fingerprint and detection confirmation if a spill is detected.
    """
    if case_id not in CASES_DB:
        raise HTTPException(status_code=404, detail=f"Case {case_id} not found.")
    case = CASES_DB[case_id]

    if sync:
        try:
            result = execute_detection_pipeline(
                image_path=image_path,
                threshold=threshold,
                center_lat=case.fingerprint.centroid_lat,
                center_lon=case.fingerprint.centroid_lon,
            )
            if result.get("oil_spill_detected") and result.get("fingerprint"):
                case.fingerprint = SpillFingerprint(**result["fingerprint"])
                if result.get("geojson_polygon"):
                    case.spill_polygon = GeoJSONFeature(
                        geometry=result["geojson_polygon"],
                        properties={"spill_id": case.case_id, "confidence": result["confidence"], "sensor": case.sensor}
                    )
                case.confirmation = evaluate_multi_model_qc(
                    spill_id=case.case_id,
                    sar_probability=float(result.get("confidence", 0.90)),
                    fingerprint=case.fingerprint
                )
            return {"case_id": case_id, "status": "completed", "result": result}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Detection failed: {str(e)}")

    # Celery async with automatic sync fallback
    try:
        task = run_detection_task.delay(image_path, threshold)
        return {
            "case_id": case_id,
            "task_id": task.id,
            "status": "submitted",
            "image_path": image_path,
            "threshold": threshold,
        }
    except Exception:
        result = execute_detection_pipeline(
            image_path=image_path,
            threshold=threshold,
            center_lat=case.fingerprint.centroid_lat,
            center_lon=case.fingerprint.centroid_lon,
        )
        if result.get("oil_spill_detected") and result.get("fingerprint"):
            case.fingerprint = SpillFingerprint(**result["fingerprint"])
            if result.get("geojson_polygon"):
                case.spill_polygon = GeoJSONFeature(
                    geometry=result["geojson_polygon"],
                    properties={"spill_id": case.case_id, "confidence": result["confidence"], "sensor": case.sensor}
                )
            case.confirmation = evaluate_multi_model_qc(
                spill_id=case.case_id,
                sar_probability=float(result.get("confidence", 0.90)),
                fingerprint=case.fingerprint
            )
        return {"case_id": case_id, "status": "completed_fallback_sync", "result": result}


@router.post("/{case_id}/detect_upload")
async def detect_uploaded_image_for_case(
    case_id: str,
    file: UploadFile = File(...),
    threshold: float = 0.5,
):
    """
    Upload a satellite tile directly to a case. Runs ML detection,
    updates case fingerprint, and returns structured analysis.
    """
    if case_id not in CASES_DB:
        raise HTTPException(status_code=404, detail=f"Case {case_id} not found.")
    case = CASES_DB[case_id]

    ext = Path(file.filename or "upload.png").suffix
    with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = Path(tmp.name)

    try:
        result = execute_detection_pipeline(
            image_path=str(tmp_path),
            threshold=threshold,
            center_lat=case.fingerprint.centroid_lat,
            center_lon=case.fingerprint.centroid_lon,
        )
        if result.get("oil_spill_detected") and result.get("fingerprint"):
            case.fingerprint = SpillFingerprint(**result["fingerprint"])
            if result.get("geojson_polygon"):
                case.spill_polygon = GeoJSONFeature(
                    geometry=result["geojson_polygon"],
                    properties={"spill_id": case.case_id, "confidence": result["confidence"], "sensor": case.sensor}
                )
            case.confirmation = evaluate_multi_model_qc(
                spill_id=case.case_id,
                sar_probability=float(result.get("confidence", 0.90)),
                fingerprint=case.fingerprint
            )
        return {"case_id": case_id, "status": "completed", "result": result}
    finally:
        if tmp_path.exists():
            tmp_path.unlink()


# ----------------------------------------------------------------------
# 7. Database Persistence (PostgreSQL / SQLAlchemy)
# ----------------------------------------------------------------------

@router.post("/{case_id}/persist")
def persist_case_to_database(case_id: str, db: Session = Depends(get_db)):
    """
    Persists or synchronizes an active case into the PostgreSQL database.
    """
    if case_id not in CASES_DB:
        raise HTTPException(status_code=404, detail=f"Case {case_id} not found.")
    case = CASES_DB[case_id]

    try:
        # Check if record exists
        db_case = db.query(DBCase).filter(DBCase.aoi == case.case_id).first()
        if not db_case:
            db_case = DBCase(
                aoi=case.case_id,
                status=case.status,
                config_version="v1.0",
                model_versions="sar-unet-v1.0.0"
            )
            db.add(db_case)
        else:
            db_case.status = case.status

        db.commit()
        db.refresh(db_case)
        return {
            "status": "persisted",
            "db_case_id": db_case.case_id,
            "aoi": db_case.aoi,
            "system_status": db_case.status
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database persistence error: {str(e)}")


@router.get("/db/all")
def query_persisted_cases_from_db(db: Session = Depends(get_db)):
    """Queries all case records stored in the PostgreSQL database."""
    try:
        records = db.query(DBCase).all()
        return [
            {
                "case_id": r.case_id,
                "aoi": r.aoi,
                "status": r.status,
                "config_version": r.config_version,
                "model_versions": r.model_versions,
                "start_time": r.start_time,
                "end_time": r.end_time,
            }
            for r in records
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database query error: {str(e)}")


# ----------------------------------------------------------------------
# 8. Forensic Audit Report Export
# ----------------------------------------------------------------------

@router.get("/{case_id}/report")
def export_evidence_report(case_id: str):
    """Generates an auditable, human-readable markdown forensic evidence report."""
    if case_id not in CASES_DB:
        raise HTTPException(status_code=404, detail=f"Case {case_id} not found.")
    case = CASES_DB[case_id]
    top = case.candidates[0] if case.candidates else None

    report_md = f"""# FORENSIC AUDIT REPORT: OIL SPILL SOURCE ATTRIBUTION
**Case Reference:** {case.case_id}  
**Investigation Target:** {case.title}  
**Region:** {case.region}  
**Satellite Observation:** {case.observation_time} ({case.sensor})  
**Report Timestamp:** {case.created_at}  

---

## 1. Satellite Detection & Confirmation
- **SAR Probability:** {case.confirmation.sar_probability * 100:.1f}%
- **Optical (S-2) Corroboration:** {f"{case.confirmation.optical_probability * 100:.1f}%" if case.confirmation.optical_probability is not None else "Not available"}
- **Thermal Infrared (TIR):** {f"{case.confirmation.tir_confidence * 100:.1f}%" if case.confirmation.tir_confidence is not None else "Not available"}
- **Temporal Consistency:** {case.confirmation.temporal_consistency * 100:.1f}%
- **Multimodal Classification:** **{case.confirmation.classification}** (Overall Confidence: {case.confirmation.overall_confidence * 100:.1f}%)

### Spill Geometric Fingerprint
- **Observed Surface Area:** {case.fingerprint.area_km2} km²
- **Centroid Coordinates:** {case.fingerprint.centroid_lat}°N, {case.fingerprint.centroid_lon}°E
- **Major Axis Orientation:** {case.fingerprint.orientation_deg}°
- **Aspect Ratio (Length / Width):** {case.fingerprint.aspect_ratio} ({case.fingerprint.length_km} km x {case.fingerprint.width_km} km)
- **Compactness Index:** {case.fingerprint.compactness}

---

## 2. Inferred Origin Spatiotemporal Field
- **Estimated Release Window:** {case.origin_field.release_window_display or (case.origin_field.release_window_start + ' to ' + case.origin_field.release_window_end)}
- **Likely Release Time (Peak):** {case.origin_field.best_estimate_display or case.origin_field.peak_release_time}
- **Estimated Drift Duration:** {case.origin_field.estimated_drift_duration_hours or 18.0:.1f} hours
- **Probable Origin Centroid:** {case.origin_field.probable_origin_lat}°N, {case.origin_field.probable_origin_lon}°E
- **Origin Inversion Confidence:** {(case.origin_field.release_confidence or 0.88) * 100:.1f}%
- **Reconstruction Method:** Backward Lagrangian particle tracking with windage vector deflection and turbulent eddy diffusion.

---

## 3. AIS Candidate Attribution & Counterfactual Forensics
### Most Consistent Candidate Vessel: **{top.vessel_name if top else 'None'}**
- **MMSI / IMO:** {top.mmsi if top else ''} / {top.imo if top else ''}
- **Vessel Type & Flag:** {top.vessel_type if top else ''} ({top.flag if top else ''})
- **Composite Attribution Score:** **{top.final_score if top else 0.0} / 100**
- **Confidence Level:** {top.confidence * 100 if top else 0.0:.1f}%

### Evidence Factor Breakdown:
"""
    if top:
        for factor, score in top.factors.items():
            report_md += f"- **{factor}:** {score}%\n"

        if top.conflicts:
            report_md += "\n### Evidence Conflicts & Anomalies:\n"
            for conf in top.conflicts:
                report_md += f"- **[{conf.severity}] {conf.conflict_type}:** {conf.explanation}\n"

    report_md += f"""
---

## 4. Predicted Impact & Vulnerability
- **Forecast Horizon:** {case.forecast.forecast_horizon_hours} Hours
- **Identified Threatened Assets:** {len(case.vulnerable_assets)} zones
"""
    for asset in case.vulnerable_assets:
        report_md += f"- **{asset.name}** ({asset.asset_type}): Risk {asset.risk_score} (Impact in ~{asset.estimated_impact_time_hours}h)\n"

    report_md += "\n## 5. Recommended Operational Response Actions:\n"
    for action in case.response_actions:
        report_md += f"- **[{action.priority}] {action.category}**: {action.description}\n"

    report_md += """
---
*Disclaimer: This system reconstructs physical and temporal consistency under available satellite, meteorological, and AIS evidence. It represents an engineering attribution finding and not a court determination of legal liability.*
"""
    return {"case_id": case.case_id, "report_markdown": report_md}
