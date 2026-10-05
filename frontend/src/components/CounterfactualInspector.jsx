import React from 'react';
import { Cpu, GitCompare, CheckCircle, AlertTriangle, ArrowRight } from 'lucide-react';

export default function CounterfactualInspector({ selectedCandidate, observedFingerprint }) {
  if (!selectedCandidate || !observedFingerprint) return null;

  const simMetrics = {
    centroid_error_km: 1.85,
    iou_score: 0.82,
    boundary_hausdorff_km: 2.1,
    orientation_delta_deg: 3.2,
    area_ratio: 0.94,
    ...selectedCandidate.matching_metrics
  };

  return (
    <div className="glass-panel" style={{ padding: '16px', display: 'flex', flexDirection: 'column', gap: '12px' }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Cpu size={18} color="var(--accent-purple)" />
          <h3 style={{ fontSize: '14px', fontWeight: 700, color: 'var(--text-primary)' }}>
            Counterfactual Simulation Inspector
          </h3>
        </div>
        <span className="badge" style={{ background: 'rgba(124, 58, 237, 0.12)', color: '#7c3aed', border: '1px solid rgba(124, 58, 237, 0.3)' }}>
          Candidate: {selectedCandidate.vessel_name}
        </span>
      </div>

      <p style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>
        Forward Lagrangian dispersion: candidate discharge simulated forward to satellite SAR observation time.
      </p>

      {/* Observed vs Simulated Metrics Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '8px' }}>
        <div style={{ background: 'var(--bg-secondary)', padding: '10px', borderRadius: '8px', border: '1px solid var(--border-color)' }}>
          <span style={{ fontSize: '10px', color: 'var(--text-muted)' }}>Centroid Offset</span>
          <div style={{ fontSize: '15px', fontWeight: 700, color: simMetrics.centroid_error_km < 3.0 ? 'var(--accent-emerald)' : 'var(--accent-rose)', marginTop: '2px' }}>
            {simMetrics.centroid_error_km} <span style={{ fontSize: '10px', color: 'var(--text-muted)' }}>km</span>
          </div>
          <span style={{ fontSize: '9px', color: 'var(--text-muted)' }}>Lower is better</span>
        </div>

        <div style={{ background: 'var(--bg-secondary)', padding: '10px', borderRadius: '8px', border: '1px solid var(--border-color)' }}>
          <span style={{ fontSize: '10px', color: 'var(--text-muted)' }}>Polygon IoU</span>
          <div style={{ fontSize: '15px', fontWeight: 700, color: 'var(--accent-cyan)', marginTop: '2px' }}>
            {(simMetrics.iou_score * 100).toFixed(1)}%
          </div>
          <span style={{ fontSize: '9px', color: 'var(--text-muted)' }}>Shape overlap</span>
        </div>

        <div style={{ background: 'var(--bg-secondary)', padding: '10px', borderRadius: '8px', border: '1px solid var(--border-color)' }}>
          <span style={{ fontSize: '10px', color: 'var(--text-muted)' }}>Orientation Delta</span>
          <div style={{ fontSize: '15px', fontWeight: 700, color: simMetrics.orientation_delta_deg < 10.0 ? 'var(--accent-emerald)' : 'var(--accent-amber)', marginTop: '2px' }}>
            {simMetrics.orientation_delta_deg}°
          </div>
          <span style={{ fontSize: '9px', color: 'var(--text-muted)' }}>Major axis diff</span>
        </div>
      </div>

      {/* Attribution Factor Breakdown */}
      {selectedCandidate.factors && (
        <div style={{ background: 'var(--bg-secondary)', padding: '10px 12px', borderRadius: '8px', border: '1px solid var(--border-color)' }}>
          <span style={{ fontSize: '11px', fontWeight: 700, color: 'var(--text-secondary)', display: 'block', marginBottom: '8px' }}>
            Forensic Factor Attribution:
          </span>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', fontSize: '11px' }}>
            {Object.entries(selectedCandidate.factors).map(([factor, score]) => (
              <div key={factor} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ color: 'var(--text-muted)' }}>{factor}:</span>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <div style={{ width: '80px', height: '5px', background: 'rgba(0, 0, 0, 0.08)', borderRadius: '3px', overflow: 'hidden' }}>
                    <div style={{
                      width: `${Math.min(100, score)}%`,
                      height: '100%',
                      background: score > 75 ? 'var(--accent-emerald)' : score > 45 ? 'var(--accent-cyan)' : 'var(--accent-rose)'
                    }} />
                  </div>
                  <span style={{ color: 'var(--text-primary)', fontWeight: 700, minWidth: '35px', textAlign: 'right' }}>{score}%</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Physics Validation Summary Banner */}
      <div style={{
        background: 'rgba(124, 58, 237, 0.08)',
        border: '1px solid rgba(124, 58, 237, 0.25)',
        borderRadius: '8px',
        padding: '10px 12px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <GitCompare size={16} color="var(--accent-purple)" />
          <span style={{ fontSize: '12px', fontWeight: 700, color: 'var(--text-primary)' }}>
            Fingerprint Similarity Score:
          </span>
        </div>
        <div style={{ fontSize: '16px', fontWeight: 800, color: 'var(--accent-purple)' }}>
          {selectedCandidate.counterfactual_score}%
        </div>
      </div>
    </div>
  );
}
