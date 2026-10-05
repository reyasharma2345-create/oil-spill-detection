"""
AEGIS-SPILL FastAPI Model Inference Endpoint
Provides high-performance synchronous prediction for uploaded satellite imagery.
Caches the PyTorch model singleton in memory so loading happens once.
Generates GeoJSON spatial polygon features and geometric fingerprinting for the WebGIS console.
"""
import io
import uuid
from pathlib import Path
from typing import Dict, Any, Optional
import numpy as np
from fastapi import APIRouter, File, UploadFile, HTTPException, Query
from PIL import Image

# Use ml inference engine and backend domain engines
from ml.inference.predict import get_default_predictor
from app.modules.detection.polygonizer import mask_to_geojson_polygon
from app.modules.fingerprint.fingerprint_engine import analyze_spill_fingerprint

router = APIRouter(tags=["ml-detection"])

ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".npy"}


@router.post("/predict")
async def predict_oil_spill(
    file: UploadFile = File(..., description="Satellite image (.png, .jpg, .tif) or NumPy array (.npy)"),
    threshold: Optional[float] = Query(0.25, ge=0.0, le=1.0, description="Slick detection confidence threshold"),
    center_lat: Optional[float] = Query(28.6500, description="Reference center latitude (WGS84)"),
    center_lon: Optional[float] = Query(-89.4200, description="Reference center longitude (WGS84)"),
    km_span: Optional[float] = Query(15.0, description="Estimated spatial extent in km"),
) -> Dict[str, Any]:
    """
    Accepts an uploaded satellite image tile and returns real-time oil spill detection,
    pixel segmentation, GeoJSON slick polygon, and geometric shape fingerprint.
    """
    # 1. Validate file extension
    filename = file.filename or "uploaded_image"
    ext = Path(filename).suffix.lower()

    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file format '{ext}'. Allowed formats: {sorted(list(ALLOWED_EXTENSIONS))}"
        )

    # 2. Read bytes
    try:
        contents = await file.read()
        if len(contents) == 0:
            raise HTTPException(status_code=400, detail="Uploaded file is empty.")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to read upload: {str(e)}")

    # 3. Parse into NumPy array
    try:
        if ext == ".npy":
            buf = io.BytesIO(contents)
            image_array = np.load(buf)
        else:
            buf = io.BytesIO(contents)
            pil_img = Image.open(buf)
            image_array = np.array(pil_img)
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Corrupt or unreadable image file: {str(e)}"
        )

    # 4. Run inference using cached singleton
    try:
        predictor = get_default_predictor()
        unique_id = f"{Path(filename).stem}_{uuid.uuid4().hex[:8]}"
        result = predictor.predict(
            image_input=image_array,
            threshold=threshold,
            save_outputs=True,
            output_prefix=unique_id,
        )

        # 5. Extract GeoJSON Polygon and Fingerprint if oil detected
        geojson_geom = None
        fingerprint_data = None
        classification = "NO_OIL"

        if result.get("oil_spill_detected"):
            # Load binary mask from npy mask output
            preds_dir = predictor.cfg.OUTPUTS_DIR / "predictions"
            mask_npy_file = preds_dir / f"{unique_id}_mask.npy"
            if mask_npy_file.exists():
                binary_mask = np.load(mask_npy_file)
                geojson_geom = mask_to_geojson_polygon(
                    binary_mask,
                    center_lat=center_lat,
                    center_lon=center_lon,
                    km_span=km_span,
                )
                if geojson_geom:
                    fp = analyze_spill_fingerprint(
                        spill_id=f"SPILL-{unique_id}",
                        geojson_geom=geojson_geom
                    )
                    fingerprint_data = fp.model_dump()

            confidence = result.get("confidence", 0.0)
            if confidence >= 0.6 and result.get("spill_area_pixels", 0) >= 30:
                classification = "OIL"
            else:
                classification = "LOOK-ALIKE"

        result["classification"] = classification
        result["geojson_geometry"] = geojson_geom
        result["fingerprint"] = fingerprint_data
        result["mask_url"] = f"/static/predictions/{unique_id}_mask.png"
        result["overlay_url"] = f"/static/predictions/{unique_id}_overlay.png"

        return result
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"ML Inference failure: {str(e)}"
        )
