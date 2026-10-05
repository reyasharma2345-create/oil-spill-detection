from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

class GeoJSONGeometry(BaseModel):
    type: str  # Point, Polygon, MultiPolygon, LineString
    coordinates: Any

class GeoJSONFeature(BaseModel):
    type: str = "Feature"
    geometry: GeoJSONGeometry
    properties: Dict[str, Any] = Field(default_factory=dict)

class GeoJSONFeatureCollection(BaseModel):
    type: str = "FeatureCollection"
    features: List[GeoJSONFeature]

class SpillFingerprint(BaseModel):
    spill_id: str
    area_km2: float
    perimeter_km: float
    centroid_lat: float
    centroid_lon: float
    orientation_deg: float
    length_km: float
    width_km: float
    compactness: float
    aspect_ratio: float
    boundary_points: List[List[float]] = Field(default_factory=list)

class DetectionConfirmation(BaseModel):
    spill_id: str
    sar_probability: float
    optical_probability: Optional[float] = None
    tir_confidence: Optional[float] = None
    optical_status: Optional[str] = "Not available"
    tir_status: Optional[str] = "Not available"
    temporal_consistency: float
    classification: str  # OIL, LOOK-ALIKE, UNCERTAIN
    overall_confidence: float
    quality_notes: List[str] = Field(default_factory=list)

class OriginProbabilityField(BaseModel):
    spill_id: str
    release_window_start: str
    release_window_end: str
    peak_release_time: str
    estimated_release_timestamp: Optional[str] = None
    estimated_drift_duration_hours: Optional[float] = None
    release_confidence: Optional[float] = None
    best_estimate_display: Optional[str] = None
    release_window_display: Optional[str] = None
    probable_origin_lat: float
    probable_origin_lon: float
    origin_polygon: GeoJSONFeature
    heatmap_grid: List[Dict[str, float]] = Field(default_factory=list)

class AISPoint(BaseModel):
    mmsi: str
    timestamp: str
    lat: float
    lon: float
    speed_knots: float
    heading_deg: float

class AISTrack(BaseModel):
    mmsi: str
    vessel_name: str
    vessel_type: str
    flag: str
    imo: Optional[str] = None
    points: List[AISPoint]
    has_gap: bool = False
    gap_details: Optional[str] = None

class FeasibilityResult(BaseModel):
    mmsi: str
    vessel_name: Optional[str] = None
    is_feasible: bool
    required_speed_knots: float
    max_observed_speed_knots: float
    min_distance_to_origin_km: float
    time_delta_hours: float
    closest_passage_time: Optional[str] = None
    closest_passage_coords: Optional[List[float]] = None
    temporal_offset_hours: Optional[float] = None
    rejection_reasons: List[str] = Field(default_factory=list)

class SimulationMatchMetrics(BaseModel):
    centroid_error_km: float
    iou_score: float
    boundary_hausdorff_km: float
    orientation_delta_deg: float
    area_ratio: float
    similarity_score: float

class CounterfactualSimulation(BaseModel):
    simulation_id: str
    mmsi: str
    vessel_name: str
    hypothetical_release_time: str
    hypothetical_release_lat: float
    hypothetical_release_lon: float
    simulated_footprint: GeoJSONFeature
    matching_metrics: SimulationMatchMetrics
    particles: List[List[float]] = Field(default_factory=list)

class RobustnessMetric(BaseModel):
    mmsi: str
    mean_similarity_score: float
    score_dispersion: float
    top_rank_frequency_pct: float
    stability_rating: str  # High, Moderate, Sensitive

class ConflictAlert(BaseModel):
    conflict_type: str  # AIS_GAP, SPEED_ANOMALY, SIMULATION_MISMATCH, SATELLITE_NOISE, WEATHER_HIGH_VARIANCE
    severity: str      # CRITICAL, HIGH, MEDIUM, LOW
    metric: str
    explanation: str

class CandidateEvidence(BaseModel):
    mmsi: str
    vessel_name: str
    vessel_type: str
    flag: str
    imo: Optional[str] = None
    rank: int
    final_score: float
    confidence: float
    pre_score: float
    counterfactual_score: float
    robustness_score: float
    factors: Dict[str, float]
    conflicts: List[ConflictAlert] = Field(default_factory=list)
    simulated_footprint: Optional[GeoJSONFeature] = None

class DriftForecast(BaseModel):
    spill_id: str
    forecast_horizon_hours: int
    corridor_polygon: GeoJSONFeature
    particle_paths: List[List[List[float]]] = Field(default_factory=list)

class VulnerableAsset(BaseModel):
    asset_id: str
    name: str
    asset_type: str  # COASTLINE, MARINE_RESERVE, FISHING_GROUND, PORT, INFRASTRUCTURE
    vulnerability_level: str  # CRITICAL, HIGH, MEDIUM, LOW
    estimated_impact_time_hours: float
    risk_score: float
    geometry: GeoJSONFeature

class ResponseAction(BaseModel):
    action_id: str
    priority: str  # IMMEDIATE, HIGH, MEDIUM
    category: str  # BOOM_DEPLOYMENT, SKIMMER_DISPATCH, COASTAL_PROTECTION, VESSEL_INTERCEPTION
    target_area: str
    description: str
    rationale: str

class SpillCase(BaseModel):
    case_id: str
    title: str
    region: str
    aoi_bounds: List[float]  # [min_lon, min_lat, max_lon, max_lat]
    observation_time: str
    sensor: str = "Sentinel-1 SAR"
    status: str = "COMPLETED"
    
    spill_polygon: GeoJSONFeature
    fingerprint: SpillFingerprint
    confirmation: DetectionConfirmation
    origin_field: OriginProbabilityField
    ais_tracks: List[AISTrack]
    candidates: List[CandidateEvidence]
    forecast: DriftForecast
    vulnerable_assets: List[VulnerableAsset]
    response_actions: List[ResponseAction]
    
    created_at: str
    config_version: str = "v1.0.0"
