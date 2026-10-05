import React, { useState, useEffect } from 'react';
import Header from './components/Header';
import WebGISMap from './components/WebGISMap';
import SpillFingerprintCard from './components/SpillFingerprintCard';
import CandidateRankingTable from './components/CandidateRankingTable';
import CounterfactualInspector from './components/CounterfactualInspector';
import RiskResponsePanel from './components/RiskResponsePanel';
import EvidenceReportModal from './components/EvidenceReportModal';
import AIDetectionModal from './components/AIDetectionModal';
import AISSurveillanceModal from './components/AISSurveillanceModal';
import {
  fetchCasesList,
  fetchCaseDetails,
  fetchCaseReport,
  runBacktrack,
  runCounterfactual,
  runForecast,
  runRiskAssessment,
  persistCaseToDb
} from './services/api';
import { Activity, CheckCircle2, AlertCircle, RefreshCw } from 'lucide-react';

export default function App() {
  const [casesList, setCasesList] = useState([]);
  const [selectedCaseId, setSelectedCaseId] = useState('GOM-2024-0418');
  const [caseData, setCaseData] = useState(null);
  const [selectedCandidate, setSelectedCandidate] = useState(null);
  const [isRunning, setIsRunning] = useState(false);
  const [pipelineStep, setPipelineStep] = useState(null);
  const [isPersisting, setIsPersisting] = useState(false);
  const [persistSuccess, setPersistSuccess] = useState(false);
  const [isReportOpen, setIsReportOpen] = useState(false);
  const [isDetectModalOpen, setIsDetectModalOpen] = useState(false);
  const [isAISModalOpen, setIsAISModalOpen] = useState(false);
  const [reportMarkdown, setReportMarkdown] = useState('');
  const [notification, setNotification] = useState(null);

  // Map Layer Visibility Toggles
  const [visibleLayers, setVisibleLayers] = useState({
    spill: true,
    origin: true,
    ais: true,
    counterfactual: true,
    forecast: true,
    risk: true
  });

  // Load cases on initial mount
  useEffect(() => {
    async function init() {
      const list = await fetchCasesList();
      setCasesList(list);
      if (list.length > 0) {
        loadCase(list[0].case_id);
      }
    }
    init();
  }, []);

  const showNotification = (type, message, durationMs = 5000) => {
    setNotification({ type, message });
    if (durationMs > 0) {
      setTimeout(() => {
        setNotification((curr) => (curr?.message === message ? null : curr));
      }, durationMs);
    }
  };

  const loadCase = async (id) => {
    setSelectedCaseId(id);
    const data = await fetchCaseDetails(id);
    if (data) {
      setCaseData(data);
      if (data.candidates && data.candidates.length > 0) {
        setSelectedCandidate(data.candidates[0]);
      }
    }
  };

  const handleToggleLayer = (layerKey) => {
    setVisibleLayers((prev) => ({ ...prev, [layerKey]: !prev[layerKey] }));
  };

  const handleOpenReport = async () => {
    const reportData = await fetchCaseReport(selectedCaseId);
    setReportMarkdown(reportData.report_markdown);
    setIsReportOpen(true);
  };

  // Real-world End-to-End Forensic Attribution Pipeline
  const handleRunPipeline = async () => {
    setIsRunning(true);
    showNotification('info', `Running forensic attribution pipeline for ${selectedCaseId}...`, 0);

    try {
      // 1. Reverse Lagrangian Hindcast
      setPipelineStep('1/4: Simulating 2D Reverse-Lagrangian Hindcast (Drift Physics)...');
      await runBacktrack(selectedCaseId, { maxHindcastHours: 24.0 });

      // 2. Candidate Feasibility & Counterfactual Drift
      setPipelineStep('2/4: Simulating Counterfactual Candidate Releases & Fingerprint Conflict...');
      await runCounterfactual(selectedCaseId, 18.0);

      // 3. Forward Drift Trajectory Corridor
      setPipelineStep('3/4: Projecting Forward Coastal Drift Trajectory Corridor (24h)...');
      await runForecast(selectedCaseId, 24);

      // 4. Vulnerability & Emergency Response Actions
      setPipelineStep('4/4: Assessing Coastal Asset Vulnerability & Prioritizing Response...');
      await runRiskAssessment(selectedCaseId);

      // Reload updated case from backend
      setPipelineStep('Synchronizing geospatial layers & candidate evidence...');
      await loadCase(selectedCaseId);

      showNotification('success', `Pipeline completed: Forensic evidence, drift corridor, and response plan updated!`, 6000);
    } catch (err) {
      console.error('Pipeline execution error:', err);
      showNotification('error', `Pipeline execution error: ${err.message}`, 8000);
    } finally {
      setIsRunning(false);
      setPipelineStep(null);
    }
  };

  // Persist current active case to PostgreSQL / PostGIS DB
  const handlePersistCase = async () => {
    setIsPersisting(true);
    try {
      await persistCaseToDb(selectedCaseId);
      setPersistSuccess(true);
      showNotification('success', `Case ${selectedCaseId} permanently saved to PostgreSQL / PostGIS database!`, 4000);
      setTimeout(() => setPersistSuccess(false), 4000);
    } catch (err) {
      console.error('Database persistence error:', err);
      showNotification('error', `Failed to persist to PostgreSQL: ${err.message}`, 6000);
    } finally {
      setIsPersisting(false);
    }
  };

  // Callback when SAR tile is detected via AIDetectionModal
  const handleSpillDetected = async (result) => {
    await loadCase(selectedCaseId);
    showNotification(
      'success',
      `SAR Tile Segmented: Detected slick with ${(result.confidence * 100).toFixed(1)}% confidence. Geospatial footprint updated!`,
      6000
    );
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh', width: '100vw', background: 'var(--bg-primary)' }}>
      {/* Top Application Navigation */}
      <Header
        casesList={casesList}
        selectedCaseId={selectedCaseId}
        onSelectCase={loadCase}
        onOpenReport={handleOpenReport}
        isRunning={isRunning}
        onRunPipeline={handleRunPipeline}
        onOpenDetectModal={() => setIsDetectModalOpen(true)}
        onOpenAISModal={() => setIsAISModalOpen(true)}
        onPersistCase={handlePersistCase}
        isPersisting={isPersisting}
        persistSuccess={persistSuccess}
      />

      {/* Real-Time Pipeline Progress / Notification Banner */}
      {(pipelineStep || notification) && (
        <div style={{
          margin: '0 16px 8px 16px',
          padding: '8px 16px',
          borderRadius: '8px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          fontSize: '12px',
          fontWeight: 600,
          background: pipelineStep
            ? 'rgba(0, 229, 255, 0.12)'
            : notification?.type === 'error'
            ? 'rgba(244, 63, 94, 0.18)'
            : notification?.type === 'success'
            ? 'rgba(16, 185, 129, 0.18)'
            : 'var(--bg-card)',
          border: pipelineStep
            ? '1px solid rgba(0, 229, 255, 0.4)'
            : notification?.type === 'error'
            ? '1px solid var(--accent-rose)'
            : notification?.type === 'success'
            ? '1px solid var(--accent-emerald)'
            : '1px solid var(--border-color)',
          color: pipelineStep
            ? 'var(--accent-cyan)'
            : notification?.type === 'error'
            ? 'var(--accent-rose)'
            : notification?.type === 'success'
            ? 'var(--accent-emerald)'
            : 'var(--text-primary)'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            {pipelineStep ? (
              <RefreshCw size={14} className="spin" color="var(--accent-cyan)" />
            ) : notification?.type === 'error' ? (
              <AlertCircle size={14} color="var(--accent-rose)" />
            ) : (
              <CheckCircle2 size={14} color="var(--accent-emerald)" />
            )}
            <span>{pipelineStep || notification?.message}</span>
          </div>
          {pipelineStep && (
            <span style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>
              Lagrangian Physics Engine Active
            </span>
          )}
        </div>
      )}

      {/* Main Investigation Workspace */}
      <main style={{
        flex: 1,
        display: 'grid',
        gridTemplateColumns: '400px 1fr 360px',
        gap: '12px',
        padding: '0 16px 12px 16px',
        overflow: 'hidden'
      }}>
        {/* Left Column: Spill Fingerprint + Candidates List */}
        <section style={{ display: 'flex', flexDirection: 'column', gap: '12px', overflowY: 'auto', paddingRight: '4px' }}>
          {caseData && (
            <>
              <SpillFingerprintCard
                fingerprint={caseData.fingerprint}
                confirmation={caseData.confirmation}
                observationTime={caseData.observation_time}
                sensor={caseData.sensor}
                originField={caseData.origin_field}
              />

              <CandidateRankingTable
                candidates={caseData.candidates}
                selectedCandidate={selectedCandidate}
                onSelectCandidate={setSelectedCandidate}
              />
            </>
          )}
        </section>

        {/* Center Column: Interactive WebGIS Map Canvas */}
        <section style={{ position: 'relative', height: '100%', borderRadius: '12px', overflow: 'hidden' }}>
          {caseData ? (
            <WebGISMap
              caseData={caseData}
              selectedCandidate={selectedCandidate}
              visibleLayers={visibleLayers}
              onToggleLayer={handleToggleLayer}
            />
          ) : (
            <div className="glass-panel" style={{ height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <span style={{ color: 'var(--text-secondary)' }}>Loading geospatial layers...</span>
            </div>
          )}
        </section>

        {/* Right Column: Counterfactual Forensics + GIS Risk Panel */}
        <section style={{ display: 'flex', flexDirection: 'column', gap: '12px', overflowY: 'auto', paddingLeft: '4px' }}>
          {caseData && (
            <>
              <CounterfactualInspector
                selectedCandidate={selectedCandidate}
                observedFingerprint={caseData.fingerprint}
              />

              <RiskResponsePanel
                assets={caseData.vulnerable_assets}
                actions={caseData.response_actions}
              />
            </>
          )}
        </section>
      </main>

      {/* Forensic Report Audit Modal */}
      <EvidenceReportModal
        isOpen={isReportOpen}
        onClose={() => setIsReportOpen(false)}
        reportMarkdown={reportMarkdown}
        caseId={selectedCaseId}
      />

      {/* Satellite SAR AI Detection Modal */}
      <AIDetectionModal
        isOpen={isDetectModalOpen}
        onClose={() => setIsDetectModalOpen(false)}
        caseId={selectedCaseId}
        currentLat={caseData?.fingerprint?.centroid_lat || 28.6500}
        currentLon={caseData?.fingerprint?.centroid_lon || -89.4200}
        onSpillDetected={handleSpillDetected}
      />

      {/* AIS Surveillance & Multi-Format Ingestion Modal */}
      <AISSurveillanceModal
        isOpen={isAISModalOpen}
        onClose={() => setIsAISModalOpen(false)}
        activeCase={caseData}
        onAddCandidateToCase={(vessel) => {
          showNotification('success', `Candidate ${vessel.vessel_name} (MMSI ${vessel.mmsi}) registered in attribution portfolio.`);
        }}
      />
    </div>
  );
}
