import React from 'react';
import { ShieldAlert, Satellite, FileText, RefreshCw, Compass, Database, Check, Radio } from 'lucide-react';

export default function Header({
  casesList,
  selectedCaseId,
  onSelectCase,
  onOpenReport,
  isRunning,
  onRunPipeline,
  onOpenDetectModal,
  onOpenAISModal,
  onPersistCase,
  isPersisting,
  persistSuccess
}) {
  return (
    <header className="glass-panel" style={{
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      padding: '12px 20px',
      margin: '12px 16px 8px 16px',
      zIndex: 1000
    }}>
      {/* Brand & Project Identity */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
        <div style={{
          width: '42px',
          height: '42px',
          borderRadius: '10px',
          background: 'linear-gradient(135deg, rgba(0, 229, 255, 0.2), rgba(244, 63, 94, 0.3))',
          border: '1px solid var(--border-glow)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          boxShadow: '0 0 20px rgba(0, 229, 255, 0.25)'
        }}>
          <ShieldAlert size={24} color="var(--accent-cyan)" />
        </div>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <h1 style={{ fontSize: '18px', fontWeight: 800, color: 'var(--text-primary)', letterSpacing: '-0.02em' }}>
              AEGIS-SPILL
            </h1>
            <span className="badge badge-cyan" style={{ fontSize: '10px' }}>PS26143</span>
            <span className="badge badge-oil" style={{ fontSize: '10px' }}>S-1 SAR + AIS AI</span>
          </div>
          <p style={{ fontSize: '11px', color: 'var(--text-secondary)', marginTop: '2px' }}>
            AI-Based Oil Spill Detection, Reverse-Lagrangian Hindcasting & Counterfactual Attribution
          </p>
        </div>
      </div>

      {/* Pipeline Status Flow Indicator */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        gap: '6px',
        padding: '6px 12px',
        background: 'var(--bg-secondary)',
        borderRadius: '8px',
        border: '1px solid var(--border-color)',
        fontSize: '11px'
      }}>
        <span style={{ color: 'var(--accent-cyan)', fontWeight: 600 }}>SAR Detection</span>
        <span style={{ color: 'var(--text-muted)' }}>➔</span>
        <span style={{ color: 'var(--accent-emerald)', fontWeight: 600 }}>Multimodal QC</span>
        <span style={{ color: 'var(--text-muted)' }}>➔</span>
        <span style={{ color: 'var(--accent-amber)', fontWeight: 600 }}>Reverse Origin</span>
        <span style={{ color: 'var(--text-muted)' }}>➔</span>
        <span style={{ color: 'var(--accent-purple)', fontWeight: 600 }}>Counterfactual</span>
        <span style={{ color: 'var(--text-muted)' }}>➔</span>
        <span style={{ color: 'var(--accent-rose)', fontWeight: 600 }}>Risk & Response</span>
      </div>

      {/* Case Selector & Action Controls */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <Compass size={16} color="var(--accent-cyan)" />
          <select
            value={selectedCaseId}
            onChange={(e) => onSelectCase(e.target.value)}
            style={{
              background: 'var(--bg-secondary)',
              color: 'var(--text-primary)',
              border: '1px solid var(--border-color)',
              borderRadius: '8px',
              padding: '8px 12px',
              fontSize: '13px',
              fontWeight: 600,
              cursor: 'pointer',
              outline: 'none'
            }}
          >
            {casesList.map((c) => (
              <option key={c.case_id} value={c.case_id}>
                {c.case_id}: {c.title}
              </option>
            ))}
          </select>
        </div>

        {/* AI Satellite Detection Upload Modal Trigger */}
        <button
          onClick={onOpenDetectModal}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            background: 'rgba(0, 229, 255, 0.12)',
            color: 'var(--accent-cyan)',
            fontWeight: 600,
            fontSize: '12px',
            border: '1px solid rgba(0, 229, 255, 0.4)',
            borderRadius: '8px',
            padding: '8px 12px',
            cursor: 'pointer',
            transition: 'all 0.2s ease'
          }}
          title="Upload Sentinel-1 SAR Tile & Run U-Net Detection"
        >
          <Satellite size={14} color="var(--accent-cyan)" />
          SAR Tile AI
        </button>

        {/* Live AIS Maritime Surveillance Trigger */}
        <button
          onClick={onOpenAISModal}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            background: 'rgba(168, 85, 247, 0.12)',
            color: 'var(--accent-purple)',
            fontWeight: 600,
            fontSize: '12px',
            border: '1px solid rgba(168, 85, 247, 0.4)',
            borderRadius: '8px',
            padding: '8px 12px',
            cursor: 'pointer',
            transition: 'all 0.2s ease'
          }}
          title="Live AIS Maritime Surveillance & Vessel Trajectory Ingestion"
        >
          <Radio size={14} color="var(--accent-purple)" />
          AIS Feed
        </button>

        {/* Replay / Run Pipeline Button */}
        <button
          onClick={onRunPipeline}
          disabled={isRunning}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            background: isRunning ? 'var(--bg-tertiary)' : 'linear-gradient(135deg, #0284c7, #2563eb)',
            color: '#ffffff',
            fontWeight: 700,
            fontSize: '12px',
            border: 'none',
            borderRadius: '8px',
            padding: '8px 14px',
            cursor: isRunning ? 'not-allowed' : 'pointer',
            transition: 'all 0.2s ease',
            boxShadow: isRunning ? 'none' : '0 2px 10px rgba(2, 132, 199, 0.3)'
          }}
        >
          <RefreshCw size={14} className={isRunning ? 'spin' : ''} />
          {isRunning ? 'Simulating...' : 'Run Pipeline'}
        </button>

        {/* Save to PostgreSQL DB Button */}
        <button
          onClick={onPersistCase}
          disabled={isPersisting}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            background: persistSuccess ? 'rgba(5, 150, 105, 0.15)' : 'var(--bg-secondary)',
            color: persistSuccess ? 'var(--accent-emerald)' : 'var(--text-primary)',
            fontWeight: 600,
            fontSize: '12px',
            border: persistSuccess ? '1px solid var(--accent-emerald)' : '1px solid var(--border-color)',
            borderRadius: '8px',
            padding: '8px 12px',
            cursor: isPersisting ? 'not-allowed' : 'pointer',
            transition: 'all 0.2s ease'
          }}
          title="Persist Active Investigation Case to PostgreSQL Database"
        >
          {persistSuccess ? <Check size={14} color="var(--accent-emerald)" /> : <Database size={14} color="var(--accent-emerald)" />}
          {isPersisting ? 'Saving...' : persistSuccess ? 'Saved' : 'Save DB'}
        </button>

        {/* Report Export Button */}
        <button
          onClick={onOpenReport}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            background: 'var(--bg-secondary)',
            color: 'var(--text-primary)',
            fontWeight: 600,
            fontSize: '12px',
            border: '1px solid var(--border-color)',
            borderRadius: '8px',
            padding: '8px 14px',
            cursor: 'pointer',
            transition: 'all 0.2s ease'
          }}
        >
          <FileText size={14} color="var(--accent-amber)" />
          Audit Report
        </button>
      </div>
    </header>
  );
}

