from typing import List, Dict, Any
from app.models.schemas import (
    AISTrack, FeasibilityResult, CounterfactualSimulation,
    CandidateEvidence, ConflictAlert, DetectionConfirmation
)

def evaluate_evidence_and_rank(
    track: AISTrack,
    feasibility: FeasibilityResult,
    simulation: CounterfactualSimulation,
    confirmation: DetectionConfirmation
) -> CandidateEvidence:
    """
    Phase 17: Multi-Factor Scoring & Conflict Resolution Engine.
    Computes explainable attribution score, temporal alignment factor, and detects evidence conflicts.
    """
    conflicts: List[ConflictAlert] = []
    
    # 1. Evaluate Pre-score factors
    proximity_factor = max(0.0, 1.0 - (feasibility.min_distance_to_origin_km / 40.0))
    speed_factor = 1.0 if feasibility.required_speed_knots <= 18.0 else max(0.0, 1.0 - (feasibility.required_speed_knots - 18.0) / 10.0)
    alignment_factor = max(0.0, 1.0 - (simulation.matching_metrics.orientation_delta_deg / 90.0))
    
    # Temporal alignment relative to inferred release window
    temporal_offset = feasibility.temporal_offset_hours if feasibility.temporal_offset_hours is not None else 0.0
    temporal_factor = max(0.0, 1.0 - (temporal_offset / 6.0))
    
    pre_score = round((0.4 * proximity_factor + 0.25 * speed_factor + 0.2 * alignment_factor + 0.15 * temporal_factor) * 100.0, 1)
    
    # 2. Evaluate Counterfactual & Robustness
    counterfactual_score = simulation.matching_metrics.similarity_score
    
    # Simulated ensemble dispersion factor
    robustness_score = round(max(0.0, counterfactual_score * 0.95 - (5.0 if track.has_gap else 0.0)), 1)
    
    # 3. Detect Evidence Conflicts & Impossible Flags
    if not feasibility.is_feasible:
        reasons_summary = "; ".join(feasibility.rejection_reasons[:2])
        conflicts.append(ConflictAlert(
            conflict_type="IMPOSSIBLE_CANDIDATE",
            severity="CRITICAL",
            metric="Physical Feasibility",
            explanation=f"Trajectory mathematically excluded from release window: {reasons_summary}"
        ))
        
    if temporal_offset > 3.5:
        conflicts.append(ConflictAlert(
            conflict_type="TEMPORAL_MISMATCH",
            severity="HIGH",
            metric="Release Time Coincidence",
            explanation=f"Point of closest approach ({feasibility.closest_passage_time or 'N/A'}) deviates {temporal_offset:.1f}h from estimated release time."
        ))

    if track.has_gap:
        conflicts.append(ConflictAlert(
            conflict_type="AIS_GAP",
            severity="MEDIUM",
            metric="AIS Continuity",
            explanation=f"Vessel experienced an AIS transmission gap ({track.gap_details or 'Gap near release window'})."
        ))
        
    if feasibility.required_speed_knots > 18.0:
        conflicts.append(ConflictAlert(
            conflict_type="SPEED_ANOMALY",
            severity="HIGH",
            metric="Required Speed",
            explanation=f"Required transit speed to origin ({feasibility.required_speed_knots} kts) exceeds standard cruising speed."
        ))
        
    if simulation.matching_metrics.centroid_error_km > 15.0:
        conflicts.append(ConflictAlert(
            conflict_type="SIMULATION_MISMATCH",
            severity="HIGH",
            metric="Centroid Offset",
            explanation=f"Counterfactual release centroid offset ({simulation.matching_metrics.centroid_error_km} km) is high."
        ))
        
    if confirmation.classification == "LOOK-ALIKE":
        conflicts.append(ConflictAlert(
            conflict_type="SATELLITE_NOISE",
            severity="CRITICAL",
            metric="Oil Confirmation",
            explanation="Optical/TIR evidence indicates candidate feature may be a non-oil look-alike (algal bloom/wind fining)."
        ))

    # 4. Composite Final Attribution Score (0 - 100)
    conflict_penalty = sum(25.0 if c.severity == "CRITICAL" else 8.0 if c.severity == "HIGH" else 4.0 for c in conflicts)
    
    if not feasibility.is_feasible:
        # Impossible candidates are capped to near-zero with explicit disqualification
        raw_final = max(0.0, min(15.0, (0.35 * pre_score + 0.45 * counterfactual_score + 0.20 * robustness_score) - conflict_penalty))
    else:
        raw_final = (0.35 * pre_score + 0.45 * counterfactual_score + 0.20 * robustness_score) - conflict_penalty
        
    final_score = round(max(0.0, min(99.9, raw_final)), 1)
    confidence = round(max(0.05, min(0.98, confirmation.overall_confidence * (1.0 - min(80.0, conflict_penalty) / 100.0))), 2)

    factors = {
        "Origin Proximity": round(proximity_factor * 100, 1),
        "Temporal Alignment": round(temporal_factor * 100, 1),
        "Speed Feasibility": round(speed_factor * 100, 1),
        "Track Alignment": round(alignment_factor * 100, 1),
        "Counterfactual Fingerprint Match": round(counterfactual_score, 1),
        "Environmental Robustness": round(robustness_score, 1)
    }

    return CandidateEvidence(
        mmsi=track.mmsi,
        vessel_name=track.vessel_name,
        vessel_type=track.vessel_type,
        flag=track.flag,
        imo=track.imo,
        rank=1,  # updated after full list sorting
        final_score=final_score,
        confidence=confidence,
        pre_score=pre_score,
        counterfactual_score=counterfactual_score,
        robustness_score=robustness_score,
        factors=factors,
        conflicts=conflicts,
        simulated_footprint=simulation.simulated_footprint
    )
