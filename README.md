# AEGIS-SPILL: AI-Based Maritime Oil Spill Attribution System (PS26143)

Merged and optimized end-to-end system based on the SIH PS26143 Master Implementation Plan:
**Detection → Confirmation → Attribution → Counterfactual Forensics → Forecast → Risk → Response**

---

## 🌟 Key Innovations & Architecture

1. **Sentinel-1 SAR Slick Segmentation**:
   - PyTorch U-Net baseline with connected component polygonization.
   - Comprehensive **Spill Fingerprint Extraction** (Area in km², Centroid Lat/Lon, Perimeter, Compactness, Orientation angle, Length/Width Aspect Ratio).
2. **Multimodal Confirmation & Look-Alike Filter**:
   - Fusion of SAR low-backscatter signatures, Sentinel-2 RGB/NIR optical glint dampening, and Thermal Infrared (TIR) contrast.
   - Rejection of algal blooms, low-wind dark patches, and biogenic films (OIL vs LOOK-ALIKE vs UNCERTAIN).
3. **Reverse-Time Lagrangian Hindcasting**:
   - Backward virtual particle tracking driven by 2D Windage (3% rule + Coriolis deflection) and Ocean Current forcing with turbulent diffusion.
   - Generation of the **Spatial Origin Probability Field** and release-time probability distribution ($T-18\text{h}$ window).
4. **AIS Reconstruction & Impossible Vessel Engine**:
   - Historical vessel trajectory parsing around the inferred origin area and time window.
   - Physical feasibility filtering based on required transit speed, maximum vessel speed constraints, closest approach distance, and AIS continuity.
5. **Counterfactual Release Simulation (Core Forensics Innovation)**:
   - Tests candidate release hypotheses by seeding particles along the candidate's trajectory at the inferred release timestamp and forward-simulating physical transport to the SAR observation time.
   - Evaluates multi-metric **Spill Fingerprint Similarity**:
     - Centroid Offset Error ($\Delta \text{km}$)
     - Shape Overlap (Polygon Intersection over Union - IoU)
     - Boundary Hausdorff Distance
     - Major Axis Orientation Delta ($\Delta^\circ$)
     - Area Expansion Ratio
6. **Ensemble Robustness & Evidence Conflict Detector**:
   - Environmental forcing perturbation ensemble.
   - Automated conflict flagging for unexplained AIS transmitter gaps, speed anomalies, and model mismatches.
   - Transparent, auditable factor-level attribution scoring.
7. **Forward Drift Corridor Forecast & GIS Risk Response**:
   - 24-48h forward Lagrangian dispersion prediction envelope.
   - Spatial intersection with sensitive coastal assets (Mangroves, Marine Reserves, Fisheries, Commercial Ports).
   - Prioritized, explainable operational response recommendations (Boom containment, Skimmer dispatch, Vessel interception).
8. **Interactive WebGIS Console & Forensic Report Exporter**:
   - React + Leaflet interactive dark-mode GIS canvas.
   - Multi-layer toggles for SAR Slicks, Origin Probability Heatmaps, AIS Candidate Tracks, Counterfactual Footprints, Drift Corridors, and Threatened Assets.
   - One-click exportable Markdown and printable Forensic Audit Reports.

---

## 🚀 Quickstart Guide

### 1. Backend Server (FastAPI)
```bash
cd backend
py -3.14 -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```
- API Documentation: [http://localhost:8000/docs](http://localhost:8000/docs)
- Health Check: [http://localhost:8000/health](http://localhost:8000/health)

### 2. Frontend WebGIS Dashboard (Vite + React)
```bash
cd frontend
npm run dev
```
- WebGIS Console: [http://localhost:5173](http://localhost:5173)

---

## 📂 Repository Structure

```
oil-spill-attribution/
├── backend/
│   ├── app/
│   │   ├── main.py                   # FastAPI Application Entrypoint
│   │   ├── config.py                 # System Configuration & Case Settings
│   │   ├── models/schemas.py         # Pydantic Schemas (Spill, AIS, Fingerprint, etc.)
│   │   ├── api/cases.py              # REST Endpoints (/cases, /backtrack, /counterfactual, /report)
│   │   ├── modules/
│   │   │   ├── detection/            # SAR U-Net Segmentation Baseline
│   │   │   ├── fingerprint/          # Geometric Shape Fingerprinting Engine
│   │   │   ├── environment/          # 2D Wind & Ocean Current Forcing Fields
│   │   │   ├── backtrack/            # Reverse Lagrangian Hindcast & Origin Heatmap
│   │   │   ├── ais/                  # Impossible Vessel Engine & Feasibility Filter
│   │   │   ├── counterfactual/       # Forward Candidate Release Simulator & Matcher
│   │   │   ├── scoring/              # Evidence Conflict Detector & Explainable Scoring
│   │   │   ├── forecast/             # Forward Drift Corridor Predictor
│   │   │   └── risk/                 # GIS Asset Vulnerability & Response Recommendation
│   │   └── data/sample_cases.py      # Gulf of Mexico & Mumbai High Historical Cases
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── Header.jsx
│   │   │   ├── WebGISMap.jsx         # Multi-layer Leaflet GIS Canvas
│   │   │   ├── SpillFingerprintCard.jsx
│   │   │   ├── CandidateRankingTable.jsx
│   │   │   ├── CounterfactualInspector.jsx
│   │   │   ├── RiskResponsePanel.jsx
│   │   │   └── EvidenceReportModal.jsx
│   │   ├── services/api.js
│   │   ├── App.jsx
│   │   └── index.css
│   └── package.json
└── README.md
```
