import React from 'react';
import { Ship, AlertCircle, CheckCircle2, ChevronRight, Zap } from 'lucide-react';

export default function CandidateRankingTable({ candidates, selectedCandidate, onSelectCandidate }) {
  if (!candidates || candidates.length === 0) return null;

  return (
    <div className="glass-panel" style={{ padding: '16px', display: 'flex', flexDirection: 'column', gap: '12px' }}>
      {/* Table Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Ship size={18} color="var(--accent-cyan)" />
          <h3 style={{ fontSize: '14px', fontWeight: 700, color: '#fff' }}>
            Candidate Source Attribution
          </h3>
        </div>
        <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
          {candidates.length} Feasible Vessels Analyzed
        </span>
      </div>

      {/* Candidate List Cards */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', maxHeight: '340px', overflowY: 'auto' }}>
        {candidates.map((cand) => {
          const isSelected = selectedCandidate?.mmsi === cand.mmsi;
          const isTop = cand.rank === 1;

          return (
            <div
              key={cand.mmsi}
              onClick={() => onSelectCandidate(cand)}
              className="glass-panel-interactive"
              style={{
                padding: '12px',
                borderRadius: '10px',
                cursor: 'pointer',
                background: isSelected ? 'rgba(2, 132, 199, 0.08)' : 'var(--bg-secondary)',
                border: isSelected ? '1px solid var(--accent-cyan)' : '1px solid var(--border-color)',
                display: 'flex',
                flexDirection: 'column',
                gap: '8px'
              }}
            >
              {/* Row 1: Rank, Name, Score */}
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <div style={{
                    width: '24px',
                    height: '24px',
                    borderRadius: '6px',
                    background: cand.conflicts?.some(c => c.conflict_type === 'IMPOSSIBLE_CANDIDATE')
                      ? 'rgba(225, 29, 72, 0.15)'
                      : isTop ? 'var(--accent-rose)' : 'var(--bg-tertiary)',
                    color: cand.conflicts?.some(c => c.conflict_type === 'IMPOSSIBLE_CANDIDATE')
                      ? '#be123c'
                      : isTop ? '#ffffff' : 'var(--text-secondary)',
                    fontWeight: 800,
                    fontSize: '12px',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center'
                  }}>
                    #{cand.rank}
                  </div>
                  <div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                      <h4 style={{ fontSize: '13px', fontWeight: 700, color: 'var(--text-primary)' }}>
                        {cand.vessel_name}
                      </h4>
                      {cand.conflicts?.some(c => c.conflict_type === 'IMPOSSIBLE_CANDIDATE') && (
                        <span style={{ fontSize: '9px', fontWeight: 700, padding: '2px 5px', borderRadius: '4px', background: 'rgba(225, 29, 72, 0.12)', color: '#be123c', border: '1px solid rgba(225, 29, 72, 0.3)' }}>
                          DISQUALIFIED
                        </span>
                      )}
                    </div>
                    <span style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>
                      {cand.vessel_type} • {cand.flag}
                    </span>
                  </div>
                </div>

                <div style={{ textAlign: 'right' }}>
                  <div style={{
                    fontSize: '16px',
                    fontWeight: 800,
                    color: cand.final_score > 80 ? 'var(--accent-rose)' : cand.final_score > 50 ? 'var(--accent-amber)' : 'var(--text-muted)'
                  }}>
                    {cand.final_score} <span style={{ fontSize: '11px', fontWeight: 500, color: 'var(--text-muted)' }}>/100</span>
                  </div>
                  <span style={{ fontSize: '10px', color: 'var(--text-muted)' }}>
                    Conf: {(cand.confidence * 100).toFixed(0)}%
                  </span>
                </div>
              </div>

              {/* Row 2: Factor Progress Bar / Breakdown */}
              <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '6px', fontSize: '11px', color: 'var(--text-muted)' }}>
                <span>Pre: <strong style={{ color: 'var(--text-primary)' }}>{cand.pre_score}%</strong></span>
                <span>•</span>
                {cand.factors?.['Temporal Alignment'] !== undefined && (
                  <>
                    <span>Time Align: <strong style={{ color: 'var(--accent-cyan)' }}>{cand.factors['Temporal Alignment']}%</strong></span>
                    <span>•</span>
                  </>
                )}
                <span>Sim Match: <strong style={{ color: 'var(--accent-purple)' }}>{cand.counterfactual_score}%</strong></span>
                <span>•</span>
                <span>Robustness: <strong style={{ color: 'var(--accent-emerald)' }}>{cand.robustness_score}%</strong></span>
              </div>

              {/* Row 3: Conflict Alerts (if any) */}
              {cand.conflicts && cand.conflicts.length > 0 && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', marginTop: '2px' }}>
                  {cand.conflicts.map((conf, idx) => (
                    <div
                      key={idx}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: '6px',
                        fontSize: '10px',
                        padding: '4px 8px',
                        borderRadius: '4px',
                        background: conf.severity === 'CRITICAL' ? 'rgba(244, 63, 94, 0.15)' : 'rgba(245, 158, 11, 0.15)',
                        color: conf.severity === 'CRITICAL' ? '#fb7185' : '#fbbf24',
                        border: `1px solid ${conf.severity === 'CRITICAL' ? 'rgba(244, 63, 94, 0.3)' : 'rgba(245, 158, 11, 0.3)'}`
                      }}
                    >
                      <AlertCircle size={12} />
                      <span><strong>{conf.conflict_type}:</strong> {conf.explanation}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
