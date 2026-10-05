"""
Complete End-to-End Test Suite for AEGIS-SPILL Full Backend API.
Tests:
1. Health check (/health)
2. Case listing & details (/cases, /cases/{id})
3. Dynamic Lagrangian Hindcast (/cases/{id}/backtrack)
4. Dynamic Counterfactual Forensics Simulation & Scoring (/cases/{id}/counterfactual)
5. Dynamic Forward Drift Forecast & Risk Assessment (/cases/{id}/forecast, /cases/{id}/risk)
6. ML Model Inference (/predict)
7. Case Detection & File Upload (/cases/{id}/detect, /cases/{id}/detect_upload)
8. Case CRUD (POST /cases, DELETE /cases/{id})
9. Database Persistence (POST /cases/{id}/persist, GET /cases/db/all)
10. Forensic Audit Report Export (/cases/{id}/report)
"""
import sys
from pathlib import Path
import json

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "backend"))

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_complete_backend():
    print("=======================================================")
    print("STARTING FULL AEGIS-SPILL BACKEND INTEGRATION TEST")
    print("=======================================================")

    # 1. Health check
    print("\n[1/10] Testing Health Endpoint (/health)...")
    r = client.get("/health")
    assert r.status_code == 200
    print("  -> Status:", r.json())

    # 2. Case Listing & Details
    print("\n[2/10] Testing Case Listing & Details...")
    r_list = client.get("/api/v1/cases")
    assert r_list.status_code == 200
    cases = r_list.json()
    assert len(cases) >= 2
    case_id = cases[0]["case_id"]
    print(f"  -> Total Cases: {len(cases)}. Selected: {case_id}")

    r_detail = client.get(f"/api/v1/cases/{case_id}")
    assert r_detail.status_code == 200
    case_detail = r_detail.json()
    print(f"  -> Case Title: {case_detail['title']}")

    # 3. Dynamic Lagrangian Hindcast (Backtracking)
    print("\n[3/10] Testing Dynamic Lagrangian Hindcast (/backtrack)...")
    r_bt = client.post(
        f"/api/v1/cases/{case_id}/backtrack",
        params={"max_hindcast_hours": 18.0, "wind_speed_ms": 7.5, "current_speed_ms": 0.35}
    )
    assert r_bt.status_code == 200
    origin_field = r_bt.json()
    print(f"  -> Probable Origin: ({origin_field['probable_origin_lat']}, {origin_field['probable_origin_lon']})")
    print(f"  -> Heatmap Grid Points: {len(origin_field['heatmap_grid'])}")
    assert len(origin_field['heatmap_grid']) > 0

    # 4. Dynamic Counterfactual Forensics Simulation
    print("\n[4/10] Testing Dynamic Counterfactual Forensics (/counterfactual)...")
    r_cf = client.post(
        f"/api/v1/cases/{case_id}/counterfactual",
        params={"release_hours_ago": 18.0}
    )
    assert r_cf.status_code == 200
    candidates = r_cf.json()
    print(f"  -> Simulated Candidates: {len(candidates)}")
    assert len(candidates) > 0
    top_cand = candidates[0]
    print(f"  -> Top Attributed Vessel: {top_cand['vessel_name']} (Score: {top_cand['final_score']}%)")

    # 5. Dynamic Forward Drift Forecast & Risk
    print("\n[5/10] Testing Forward Drift Forecast (/forecast) & Risk Assessment (/risk)...")
    r_fc = client.post(
        f"/api/v1/cases/{case_id}/forecast",
        params={"forecast_horizon_hours": 36}
    )
    assert r_fc.status_code == 200
    forecast = r_fc.json()
    print(f"  -> Forecast Horizon: {forecast['forecast_horizon_hours']} hours")
    print(f"  -> Particle Paths: {len(forecast['particle_paths'])}")

    r_risk = client.post(f"/api/v1/cases/{case_id}/risk")
    assert r_risk.status_code == 200
    risk_data = r_risk.json()
    print(f"  -> Vulnerable Coastal Assets: {len(risk_data['vulnerable_assets'])}")
    print(f"  -> Priority Response Actions: {len(risk_data['response_actions'])}")

    # 6. ML Model Inference Endpoint (/predict)
    print("\n[6/10] Testing ML Model Inference (/predict)...")
    sar_file = project_root / "backend" / "test_sar.npy"
    with open(sar_file, "rb") as f:
        r_pred = client.post(
            "/predict",
            files={"file": ("test_sar.npy", f.read(), "application/octet-stream")},
            params={"threshold": 0.5, "center_lat": 28.65, "center_lon": -89.42}
        )
    assert r_pred.status_code == 200
    pred = r_pred.json()
    print(f"  -> ML Oil Detected: {pred['oil_spill_detected']} (Confidence: {pred['confidence']})")
    print(f"  -> Classification: {pred['classification']}")
    assert "fingerprint" in pred

    # 7. In-Case Detection & Upload
    print("\n[7/10] Testing In-Case Detection & Upload (/detect, /detect_upload)...")
    r_detect = client.post(
        f"/api/v1/cases/{case_id}/detect",
        params={"image_path": str(sar_file), "threshold": 0.5, "sync": True}
    )
    assert r_detect.status_code == 200
    print("  -> Sync Detection:", r_detect.json()["status"])

    with open(sar_file, "rb") as f:
        r_up = client.post(
            f"/api/v1/cases/{case_id}/detect_upload",
            files={"file": ("test_sar.npy", f.read(), "application/octet-stream")},
            params={"threshold": 0.5}
        )
    assert r_up.status_code == 200
    print("  -> Upload Detection:", r_up.json()["status"])

    # 8. Case CRUD (Create & Delete)
    print("\n[8/10] Testing Case CRUD (POST /cases, DELETE /cases/{id})...")
    # Clone case with new ID
    new_case_data = dict(case_detail)
    new_case_data["case_id"] = "TEST-CASE-999"
    new_case_data["title"] = "Automated Test Case"

    r_create = client.post("/api/v1/cases", json=new_case_data)
    assert r_create.status_code == 201
    print("  -> Created Case:", r_create.json()["case_id"])

    r_del = client.delete("/api/v1/cases/TEST-CASE-999")
    assert r_del.status_code == 200
    print("  -> Deleted Case:", r_del.json()["case_id"])

    # 9. Database Persistence (PostgreSQL / SQLAlchemy)
    print("\n[9/10] Testing Database Persistence (/persist, /db/all)...")
    r_persist = client.post(f"/api/v1/cases/{case_id}/persist")
    assert r_persist.status_code == 200
    print("  -> Persisted to DB:", r_persist.json())

    r_db_all = client.get("/api/v1/cases/db/all")
    assert r_db_all.status_code == 200
    db_records = r_db_all.json()
    print(f"  -> Database Persisted Records Count: {len(db_records)}")

    # 10. Forensic Audit Report Export (/report)
    print("\n[10/10] Testing Forensic Audit Report Generation (/report)...")
    r_rep = client.get(f"/api/v1/cases/{case_id}/report")
    assert r_rep.status_code == 200
    rep = r_rep.json()
    assert "FORENSIC AUDIT REPORT" in rep["report_markdown"]
    print(f"  -> Generated Report Length: {len(rep['report_markdown'])} chars")

    print("\n=======================================================")
    print("FULL BACKEND END-TO-END VERIFICATION: 10/10 PASSED!")
    print("=======================================================")

if __name__ == "__main__":
    test_complete_backend()
