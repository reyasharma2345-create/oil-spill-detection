"""
AEGIS-SPILL Copernicus Satellite Ingestion REST API
Provides endpoints to search newly acquired Sentinel-1 SAR GRD satellite passes
and automatically ingest satellite imagery directly into the oil spill attribution system.
"""
import shutil
from pathlib import Path
import tempfile
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, HTTPException, Query

from app.modules.copernicus.cdse_client import cdse_client
from app.modules.detection.polygonizer import mask_to_geojson_polygon
from app.modules.fingerprint.fingerprint_engine import analyze_spill_fingerprint
from app.models.schemas import SpillFingerprint, GeoJSONFeature
from app.api.cases import CASES_DB
from ml.inference.predict import get_default_predictor

router = APIRouter(prefix="/copernicus", tags=["copernicus-satellite-ingestion"])


@router.get("/search")
def search_copernicus_sentinel1_passes(
    case_id: Optional[str] = Query(None, description="Active Case ID to auto-populate AOI coordinates"),
    min_lon: Optional[float] = Query(None),
    min_lat: Optional[float] = Query(None),
    max_lon: Optional[float] = Query(None),
    max_lat: Optional[float] = Query(None),
    limit: int = Query(6, ge=1, le=20)
) -> Dict[str, Any]:
    """
    Queries the official Copernicus Data Space Ecosystem (CDSE) for recently acquired
    Sentinel-1 SAR GRD satellite passes over the specified bounding box.
    """
    # Safely extract numeric parameters (handles FastAPI Query instances in direct calls)
    f_min_lon = min_lon if isinstance(min_lon, (int, float)) else None
    f_min_lat = min_lat if isinstance(min_lat, (int, float)) else None
    f_max_lon = max_lon if isinstance(max_lon, (int, float)) else None
    f_max_lat = max_lat if isinstance(max_lat, (int, float)) else None
    f_case_id = case_id if isinstance(case_id, str) else None
    f_limit = limit if isinstance(limit, int) else 6

    # 1. If explicit coordinates are passed, use them directly
    has_explicit_coords = (
        f_min_lon is not None and f_min_lat is not None and
        f_max_lon is not None and f_max_lat is not None
    )

    if not has_explicit_coords and f_case_id and f_case_id in CASES_DB:
        case = CASES_DB[f_case_id]
        if case.aoi_bounds and len(case.aoi_bounds) == 4:
            f_min_lon = case.aoi_bounds[0]
            f_min_lat = case.aoi_bounds[1]
            f_max_lon = case.aoi_bounds[2]
            f_max_lat = case.aoi_bounds[3]

    # Defaults to Gulf of Mexico or Mumbai if still unassigned
    f_min_lon = f_min_lon if f_min_lon is not None else -90.02
    f_min_lat = f_min_lat if f_min_lat is not None else 28.15
    f_max_lon = f_max_lon if f_max_lon is not None else -88.82
    f_max_lat = f_max_lat if f_max_lat is not None else 29.15

    products = cdse_client.search_sentinel1_grd(
        min_lon=f_min_lon,
        min_lat=f_min_lat,
        max_lon=f_max_lon,
        max_lat=f_max_lat,
        max_results=f_limit
    )

    return {
        "status": "success",
        "aoi_bbox": [f_min_lon, f_min_lat, f_max_lon, f_max_lat],
        "products_count": len(products),
        "products": products
    }


@router.post("/ingest-and-detect")
def ingest_copernicus_scene_into_case(
    product_id: str = Query(..., description="CDSE Product UUID"),
    product_name: str = Query(..., description="CDSE Product Name"),
    quicklook_url: Optional[str] = Query(None, description="Direct CDSE Quicklook Asset URL"),
    case_id: Optional[str] = Query(None, description="Optional Case ID to update"),
    threshold: float = Query(0.35, ge=0.0, le=1.0)
) -> Dict[str, Any]:
    """
    Ingests a discovered Copernicus Sentinel-1 SAR scene, runs the trained SAR U-Net
    segmentation detector, generates slick polygons & shape fingerprints, and optionally
    updates the active case.
    """
    f_threshold = threshold if isinstance(threshold, (int, float)) else 0.35
    f_quicklook = quicklook_url if isinstance(quicklook_url, str) else None
    f_case_id = case_id if isinstance(case_id, str) else None

    tmp_dir = Path(tempfile.gettempdir()) / "aegis_copernicus"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    quicklook_file = tmp_dir / f"{product_name}_ql.png"

    # 1. Download quicklook from Copernicus
    success = cdse_client.download_quicklook(
        product_id=str(product_id),
        product_name=str(product_name),
        dest_path=quicklook_file,
        quicklook_url=f_quicklook
    )
    if not success:
        raise HTTPException(
            status_code=502,
            detail=f"Failed to fetch satellite preview from Copernicus CDSE for product {product_name}."
        )

    # Copy input tile to static predictions directory so browser can load it without CORS/CORB blocks
    workspace_root = Path(__file__).resolve().parent.parent.parent.parent
    static_preds_dir = workspace_root / "outputs" / "predictions"
    static_preds_dir.mkdir(parents=True, exist_ok=True)
    
    clean_stem = "".join([c if c.isalnum() or c in ("-", "_") else "_" for c in str(product_name)[:24]])
    prefix = f"cdse_{clean_stem}"
    local_input_file = static_preds_dir / f"{prefix}_input.png"
    try:
        shutil.copyfile(quicklook_file, local_input_file)
        local_input_url = f"/static/predictions/{local_input_file.name}"
    except Exception:
        local_input_url = None

    # 2. Run trained SAR U-Net inference
    try:
        predictor = get_default_predictor()
        pred_result = predictor.predict(
            image_input=quicklook_file,
            threshold=f_threshold,
            save_outputs=True,
            output_prefix=prefix
        )
        if pred_result.get("overlay_path"):
            pred_result["overlay_url"] = f"/static/predictions/{Path(pred_result['overlay_path']).name}"
        if pred_result.get("mask_path"):
            pred_result["mask_url"] = f"/static/predictions/{Path(pred_result['mask_path']).name}"
        if local_input_url:
            pred_result["input_tile_url"] = local_input_url
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Inference error on ingested scene: {str(e)}")

    # 3. If updating a case, bind new polygon & fingerprint
    if case_id and case_id in CASES_DB and pred_result.get("oil_spill_detected"):
        case = CASES_DB[case_id]
        # Polygonize mask
        preds_dir = predictor.cfg.OUTPUTS_DIR / "predictions"
        mask_file = next(preds_dir.glob(f"{prefix}*_mask.npy"), None)
        if mask_file and mask_file.exists():
            import numpy as np
            binary_mask = np.load(mask_file)
            center_lat = case.fingerprint.centroid_lat if case.fingerprint else 28.6500
            center_lon = case.fingerprint.centroid_lon if case.fingerprint else -89.4200
            geojson_poly = mask_to_geojson_polygon(
                binary_mask,
                center_lat=center_lat,
                center_lon=center_lon,
                km_span=15.0
            )
            if geojson_poly:
                fp = analyze_spill_fingerprint(f"SPILL-CDSE-{case.case_id}", geojson_poly)
                case.fingerprint = fp if isinstance(fp, SpillFingerprint) else SpillFingerprint(**fp)
                case.spill_polygon = GeoJSONFeature(
                    geometry=geojson_poly,
                    properties={
                        "spill_id": case.case_id,
                        "sensor": f"Sentinel-1 C-SAR (Copernicus CDSE: {clean_stem[:16]})",
                        "confidence": pred_result["confidence"]
                    }
                )
                from app.modules.detection.multi_model_qc import evaluate_multi_model_qc
                case.confirmation = evaluate_multi_model_qc(
                    spill_id=case.case_id,
                    sar_probability=float(pred_result.get("confidence", 0.92)),
                    fingerprint=case.fingerprint
                )

    return {
        "status": "completed",
        "product_name": product_name,
        "input_tile_url": local_input_url,
        "detection": pred_result,
        "case_updated": bool(case_id and case_id in CASES_DB)
    }
