import React from 'react';
import { Target, Maximize2, Compass, Activity, ShieldCheck, AlertTriangle, Clock, MapPin } from 'lucide-react';

export default function SpillFingerprintCard({ fingerprint, confirmation, observationTime, sensor, originField }) {
  if (!fingerprint) return null;

  return (
    <div className="glass-panel" style={{ padding: '16px', display: 'flex', flexDirection: 'column', gap: '12px' }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Target size={18} color="var(--accent-rose)" />
          <h3 style={{ fontSize: '14px', fontWeight: 700, color: 'var(--text-primary)' }}>
            Spill Fingerprint & Inferred Origin
          </h3>
        </div>
        <span className="badge badge-oil">
          {confirmation?.classification || 'OIL CONFIRMED'}
        </span>
      </div>

      {/* Primary Metrics Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '8px' }}>
        <div style={{ background: 'var(--bg-secondary)', padding: '10px', borderRadius: '8px', border: '1px solid var(--border-color)' }}>
          <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Surface Area</span>
          <div style={{ fontSize: '18px', fontWeight: 800, color: 'var(--accent-rose)', marginTop: '2px' }}>
            {fingerprint.area_km2} <span style={{ fontSize: '12px', fontWeight: 500, color: 'var(--text-secondary)' }}>km²</span>
          </div>
        </div>

        <div style={{ background: 'var(--bg-secondary)', padding: '10px', borderRadius: '8px', border: '1px solid var(--border-color)' }}>
          <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Centroid (Lat, Lon)</span>
          <div style={{ fontSize: '13px', fontWeight: 700, color: 'var(--text-primary)', marginTop: '4px' }} className="font-mono">
            {fingerprint.centroid_lat.toFixed(4)}°, {fingerprint.centroid_lon.toFixed(4)}°
          </div>
        </div>

        <div style={{ background: 'var(--bg-secondary)', padding: '10px', borderRadius: '8px', border: '1px solid var(--border-color)' }}>
          <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Dimensions (L x W)</span>
          <div style={{ fontSize: '13px', fontWeight: 600, color: 'var(--accent-cyan)', marginTop: '3px' }}>
            {fingerprint.length_km} x {fingerprint.width_km} km
          </div>
          <span style={{ fontSize: '10px', color: 'var(--text-muted)' }}>Ratio: {fingerprint.aspect_ratio}:1</span>
        </div>

        <div style={{ background: 'var(--bg-secondary)', padding: '10px', borderRadius: '8px', border: '1px solid var(--border-color)' }}>
          <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Orientation</span>
          <div style={{ fontSize: '14px', fontWeight: 700, color: 'var(--accent-amber)', marginTop: '3px' }}>
            {fingerprint.orientation_deg}° <span style={{ fontSize: '10px', color: 'var(--text-muted)' }}>(Major Axis)</span>
          </div>
        </div>
      </div>

      {/* Phase 10: Inferred Release Date, Time & Window */}
      {originField && (
        <div style={{ background: 'rgba(2, 132, 199, 0.06)', padding: '10px 12px', borderRadius: '8px', border: '1px solid rgba(2, 132, 199, 0.25)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <Clock size={13} color="var(--accent-cyan)" />
              <span style={{ fontSize: '11px', fontWeight: 700, color: 'var(--accent-cyan)' }}>
                Estimated Release Window (Phase 10):
              </span>
            </div>
            {originField.release_confidence && (
              <span style={{ fontSize: '11px', fontWeight: 700, color: 'var(--accent-emerald)' }}>
                {(originField.release_confidence * 100).toFixed(0)}% Conf
              </span>
            )}
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '5px', fontSize: '11px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ color: 'var(--text-muted)' }}>Likely Window:</span>
              <span style={{ color: 'var(--text-primary)', fontWeight: 700, fontFamily: 'monospace' }}>
                {originField.release_window_display || `${originField.release_window_start} to ${originField.release_window_end}`}
              </span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ color: 'var(--text-muted)' }}>Best Estimate (Peak):</span>
              <span style={{ color: 'var(--accent-cyan)', fontWeight: 700, fontFamily: 'monospace' }}>
                {originField.best_estimate_display || originField.peak_release_time}
              </span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ color: 'var(--text-muted)' }}>Estimated Drift Duration:</span>
              <span style={{ color: 'var(--accent-amber)', fontWeight: 600 }}>
                {originField.estimated_drift_duration_hours ? `${originField.estimated_drift_duration_hours} hours` : '18.0 hours'}
              </span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ color: 'var(--text-muted)' }}>Probable Origin (Lat, Lon):</span>
              <span style={{ color: 'var(--text-primary)', fontWeight: 600, fontFamily: 'monospace' }}>
                {originField.probable_origin_lat?.toFixed(4)}°, {originField.probable_origin_lon?.toFixed(4)}°
              </span>
            </div>
          </div>
        </div>
      )}

      {/* Phase 7: Multimodal Sensor Fusion Confidence Breakdown */}
      {confirmation && (
        <div style={{ background: 'var(--bg-secondary)', padding: '10px 12px', borderRadius: '8px', border: '1px solid var(--border-color)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
            <span style={{ fontSize: '11px', fontWeight: 600, color: 'var(--text-secondary)' }}>Multimodal Sensor QC (Phase 7):</span>
            <span style={{ fontSize: '12px', fontWeight: 800, color: 'var(--accent-emerald)' }}>
              {(confirmation.overall_confidence * 100).toFixed(1)}% Confidence
            </span>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', fontSize: '11px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ color: 'var(--text-muted)' }}>Sentinel-1 SAR C-Band:</span>
              <span style={{ color: 'var(--text-primary)', fontWeight: 600 }}>{(confirmation.sar_probability * 100).toFixed(0)}%</span>
            </div>

            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ color: 'var(--text-muted)' }}>Sentinel-2 Optical (MSI):</span>
              <span style={{ color: confirmation.optical_probability != null ? 'var(--text-primary)' : 'var(--text-muted)', fontWeight: 600 }}>
                {confirmation.optical_probability != null ? `${(confirmation.optical_probability * 100).toFixed(0)}%` : 'Not available'}
              </span>
            </div>

            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ color: 'var(--text-muted)' }}>Thermal Infrared (TIR):</span>
              <span style={{ color: confirmation.tir_confidence != null ? 'var(--text-primary)' : 'var(--text-muted)', fontWeight: 600 }}>
                {confirmation.tir_confidence != null ? `${(confirmation.tir_confidence * 100).toFixed(0)}%` : 'Not available'}
              </span>
            </div>

            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ color: 'var(--text-muted)' }}>Temporal Persistence:</span>
              <span style={{ color: 'var(--text-primary)', fontWeight: 600 }}>{(confirmation.temporal_consistency * 100).toFixed(0)}%</span>
            </div>
          </div>
        </div>
      )}

      {/* Metadata footer */}
      <div style={{ fontSize: '10px', color: 'var(--text-muted)', display: 'flex', justifyContent: 'space-between' }}>
        <span>Obs: {observationTime}</span>
        <span>Sensor: {sensor}</span>
      </div>
    </div>
  );
}
