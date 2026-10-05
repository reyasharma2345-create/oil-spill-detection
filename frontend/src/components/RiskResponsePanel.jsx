import React from 'react';
import { AlertOctagon, Anchor, Shield, Clock, MapPin, CheckCircle2 } from 'lucide-react';

export default function RiskResponsePanel({ assets, actions }) {
  if (!assets || !actions) return null;

  return (
    <div className="glass-panel" style={{ padding: '16px', display: 'flex', flexDirection: 'column', gap: '12px' }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <AlertOctagon size={18} color="var(--accent-rose)" />
          <h3 style={{ fontSize: '14px', fontWeight: 700, color: 'var(--text-primary)' }}>
            GIS Vulnerability & Response Actions
          </h3>
        </div>
        <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
          24h Forward Horizon
        </span>
      </div>

      {/* Threatened Assets List */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
        <span style={{ fontSize: '11px', fontWeight: 600, color: 'var(--text-secondary)', textTransform: 'uppercase' }}>
          Threatened Sensitive Assets:
        </span>
        {assets.map((asset) => (
          <div
            key={asset.asset_id}
            style={{
              padding: '8px 10px',
              borderRadius: '6px',
              background: 'var(--bg-secondary)',
              border: '1px solid var(--border-color)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              fontSize: '11px'
            }}
          >
            <div>
              <div style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{asset.name}</div>
              <span style={{ color: 'var(--text-muted)', fontSize: '10px' }}>{asset.asset_type}</span>
            </div>
            <div style={{ textAlign: 'right' }}>
              <div style={{ color: 'var(--accent-rose)', fontWeight: 700 }}>
                Risk {asset.risk_score}
              </div>
              <div style={{ color: 'var(--text-muted)', fontSize: '10px' }}>
                Impact in ~{asset.estimated_impact_time_hours}h
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Recommended Operational Actions */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', marginTop: '4px' }}>
        <span style={{ fontSize: '11px', fontWeight: 600, color: 'var(--text-secondary)', textTransform: 'uppercase' }}>
          Recommended Response Operations:
        </span>
        {actions.map((act) => (
          <div
            key={act.action_id}
            style={{
              padding: '10px',
              borderRadius: '8px',
              background: act.priority === 'IMMEDIATE' ? 'rgba(225, 29, 72, 0.08)' : 'rgba(37, 99, 235, 0.08)',
              border: `1px solid ${act.priority === 'IMMEDIATE' ? 'rgba(225, 29, 72, 0.28)' : 'rgba(37, 99, 235, 0.28)'}`,
              display: 'flex',
              flexDirection: 'column',
              gap: '4px',
              fontSize: '11px'
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <span style={{
                fontWeight: 700,
                color: act.priority === 'IMMEDIATE' ? 'var(--accent-rose)' : 'var(--accent-blue)',
                textTransform: 'uppercase',
                fontSize: '10px'
              }}>
                [{act.priority}] {act.category}
              </span>
              <span style={{ color: 'var(--text-muted)', fontSize: '10px' }}>{act.target_area}</span>
            </div>
            <div style={{ color: 'var(--text-primary)', fontWeight: 600 }}>
              {act.description}
            </div>
            <div style={{ color: 'var(--text-muted)', fontSize: '10px', fontStyle: 'italic' }}>
              Rationale: {act.rationale}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
