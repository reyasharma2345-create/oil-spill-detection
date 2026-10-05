import React, { useState, useEffect } from 'react';
import { 
  Radio, Ship, Upload, AlertTriangle, CheckCircle2, XCircle,
  Search, ShieldAlert, Compass, Navigation, RefreshCw, FileText, Check, ArrowRight
} from 'lucide-react';

export default function AISSurveillanceModal({
  isOpen,
  onClose,
  activeCase,
  onAddCandidateToCase
}) {
  const [activeTab, setActiveTab] = useState('surveillance'); // 'surveillance' | 'upload' | 'feasibility'
  const [loading, setLoading] = useState(false);
  const [vessels, setVessels] = useState([]);
  const [uploadResult, setUploadResult] = useState(null);
  const [fileToUpload, setFileToUpload] = useState(null);
  const [lookbackHours, setLookbackHours] = useState(24);
  const [statusMsg, setStatusMsg] = useState('');
  const [selectedVessel, setSelectedVessel] = useState(null);

  // Derive bounding box from active case fingerprint
  const aoiBbox = activeCase ? [
    (activeCase.fingerprint.centroid_lon - 0.8).toFixed(2),
    (activeCase.fingerprint.centroid_lat - 0.6).toFixed(2),
    (activeCase.fingerprint.centroid_lon + 0.8).toFixed(2),
    (activeCase.fingerprint.centroid_lat + 0.6).toFixed(2)
  ].join(',') : '71.5,18.0,73.5,19.8';

  // Automatically fetch vessels in AOI on mount
  useEffect(() => {
    if (isOpen && activeCase) {
      handleQueryVessels();
    }
  }, [isOpen, activeCase]);

  const handleQueryVessels = async () => {
    setLoading(true);
    setStatusMsg('Querying maritime AIS surveillance feed...');
    try {
      const caseParam = activeCase ? `&case_id=${activeCase.case_id}` : '';
      const res = await fetch(`/api/v1/ais/tracks?bbox=${aoiBbox}&lookback_hours=${lookbackHours}${caseParam}`);
      if (!res.ok) throw new Error(`HTTP Error ${res.status}`);
      const data = await res.json();
      setVessels(data);
      setStatusMsg(`Successfully tracked ${data.length} vessels in maritime zone.`);
    } catch (err) {
      setStatusMsg(`Failed to query AIS feed: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  const handleFileUpload = async (e) => {
    e.preventDefault();
    if (!fileToUpload) return;

    setLoading(true);
    setStatusMsg(`Parsing AIS file: ${fileToUpload.name}...`);
    const formData = new FormData();
    formData.append('file', fileToUpload);

    try {
      const res = await fetch('/api/v1/ais/upload', {
        method: 'POST',
        body: formData
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Upload failed');
      setUploadResult(data);
      setStatusMsg(`Successfully decoded ${data.vessels_parsed} vessel pings!`);
      // Refresh list
      handleQueryVessels();
    } catch (err) {
      setStatusMsg(`Upload failed: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div style={{
      position: 'fixed',
      top: 0,
      left: 0,
      width: '100vw',
      height: '100vh',
      background: 'rgba(15, 23, 42, 0.45)',
      backdropFilter: 'blur(10px)',
      zIndex: 9999,
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      padding: '24px'
    }}>
      <div style={{
        width: '920px',
        maxHeight: '88vh',
        background: 'var(--bg-card)',
        border: '1px solid var(--border-color)',
        borderRadius: '16px',
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden',
        boxShadow: '0 25px 60px -15px rgba(0, 0, 0, 0.15)'
      }}>
        {/* Modal Header */}
        <div style={{
          padding: '18px 24px',
          borderBottom: '1px solid var(--border-color)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          background: 'var(--bg-secondary)'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <div style={{
              width: '40px',
              height: '40px',
              borderRadius: '10px',
              background: 'rgba(0, 229, 255, 0.1)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              border: '1px solid rgba(0, 229, 255, 0.3)'
            }}>
              <Radio size={22} color="var(--accent-cyan)" />
            </div>
            <div>
              <h2 style={{ fontSize: '18px', fontWeight: 700, margin: 0, color: 'var(--text-primary)', display: 'flex', alignItems: 'center', gap: '8px' }}>
                AIS Maritime Surveillance & Trajectory Ingestion
                <span style={{ fontSize: '11px', background: 'rgba(0,229,255,0.15)', color: 'var(--accent-cyan)', padding: '2px 8px', borderRadius: '12px' }}>
                  Live NMEA / JSON / CSV
                </span>
              </h2>
              <div style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>
                Target AOI: {aoiBbox} ({activeCase?.region || 'Current Operational Theater'})
              </div>
            </div>
          </div>

          <button
            onClick={onClose}
            style={{
              background: 'transparent',
              border: '1px solid var(--border-color)',
              color: 'var(--text-secondary)',
              borderRadius: '8px',
              padding: '6px 12px',
              cursor: 'pointer',
              fontSize: '13px'
            }}
          >
            ✕ Close
          </button>
        </div>

        {/* Navigation Tabs */}
        <div style={{
          display: 'flex',
          borderBottom: '1px solid var(--border-color)',
          padding: '0 24px',
          background: 'var(--bg-secondary)'
        }}>
          {[
            { id: 'surveillance', label: 'Active AOI Surveillance', icon: Ship },
            { id: 'upload', label: 'Upload NMEA / CSV / JSON', icon: Upload }
          ].map(tab => {
            const Icon = tab.icon;
            const active = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px',
                  padding: '14px 18px',
                  background: 'none',
                  border: 'none',
                  borderBottom: active ? '2px solid var(--accent-cyan)' : '2px solid transparent',
                  color: active ? 'var(--accent-cyan)' : 'var(--text-secondary)',
                  fontWeight: active ? 600 : 500,
                  fontSize: '13px',
                  cursor: 'pointer'
                }}
              >
                <Icon size={16} />
                {tab.label}
              </button>
            );
          })}
        </div>

        {/* Modal Body */}
        <div style={{ padding: '20px 24px', overflowY: 'auto', flex: 1, display: 'flex', flexDirection: 'column', gap: '18px' }}>
          {statusMsg && (
            <div style={{
              padding: '10px 14px',
              borderRadius: '8px',
              fontSize: '12px',
              background: 'rgba(0, 229, 255, 0.08)',
              border: '1px solid rgba(0, 229, 255, 0.2)',
              color: 'var(--accent-cyan)',
              display: 'flex',
              alignItems: 'center',
              gap: '8px'
            }}>
              <RefreshCw size={14} className={loading ? 'spin' : ''} />
              {statusMsg}
            </div>
          )}

          {activeTab === 'surveillance' && (
            <>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '12px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px', fontSize: '13px' }}>
                  <span style={{ color: 'var(--text-secondary)' }}>Temporal History:</span>
                  <select
                    value={lookbackHours}
                    onChange={(e) => setLookbackHours(Number(e.target.value))}
                    style={{
                      background: 'var(--bg-card)',
                      border: '1px solid var(--border-color)',
                      color: 'var(--text-primary)',
                      borderRadius: '6px',
                      padding: '5px 10px',
                      fontSize: '12px'
                    }}
                  >
                    <option value={12}>Past 12 Hours</option>
                    <option value={24}>Past 24 Hours</option>
                    <option value={48}>Past 48 Hours</option>
                    <option value={72}>Past 72 Hours</option>
                  </select>
                </div>

                <button
                  onClick={handleQueryVessels}
                  disabled={loading}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '6px',
                    padding: '8px 16px',
                    borderRadius: '8px',
                    background: 'var(--accent-cyan)',
                    color: '#ffffff',
                    fontWeight: 600,
                    border: 'none',
                    cursor: 'pointer',
                    fontSize: '13px'
                  }}
                >
                  <RefreshCw size={14} className={loading ? 'spin' : ''} />
                  Refresh AIS Feed
                </button>
              </div>

              {/* Vessel Table */}
              <div style={{
                border: '1px solid var(--border-color)',
                borderRadius: '10px',
                overflow: 'hidden',
                background: 'var(--bg-secondary)'
              }}>
                <div style={{
                  display: 'grid',
                  gridTemplateColumns: '1.8fr 1.2fr 1fr 1fr 1fr 1.4fr',
                  padding: '10px 14px',
                  background: 'var(--bg-tertiary)',
                  fontSize: '11px',
                  fontWeight: 700,
                  color: 'var(--text-secondary)',
                  textTransform: 'uppercase',
                  letterSpacing: '0.05em'
                }}>
                  <div>Vessel Identity</div>
                  <div>Type / Flag</div>
                  <div>Speed (Knots)</div>
                  <div>Min Dist to Spill</div>
                  <div>AIS Gaps</div>
                  <div>Feasibility Status</div>
                </div>

                <div style={{ maxHeight: '340px', overflowY: 'auto' }}>
                  {vessels.length === 0 ? (
                    <div style={{ padding: '30px', textAlign: 'center', color: 'var(--text-muted)', fontSize: '13px' }}>
                      No vessels currently tracked in this AOI. Click Refresh or Upload custom logs.
                    </div>
                  ) : (
                    vessels.map((v) => {
                      const feas = v.feasibility;
                      const isFeasible = feas ? feas.is_feasible : true;
                      const dist = feas ? feas.min_distance_to_origin_km : (v.points?.[0]?.speed_knots || 0);

                      return (
                        <div
                          key={v.mmsi}
                          onClick={() => setSelectedVessel(v)}
                          style={{
                            display: 'grid',
                            gridTemplateColumns: '1.8fr 1.2fr 1fr 1fr 1fr 1.4fr',
                            padding: '12px 14px',
                            borderTop: '1px solid rgba(255,255,255,0.04)',
                            fontSize: '12px',
                            alignItems: 'center',
                            cursor: 'pointer',
                            background: selectedVessel?.mmsi === v.mmsi ? 'rgba(0, 229, 255, 0.08)' : 'transparent',
                            transition: 'background 0.15s ease'
                          }}
                        >
                          <div>
                            <div style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{v.vessel_name}</div>
                            <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>MMSI: {v.mmsi} | {v.imo || 'N/A'}</div>
                          </div>

                          <div>
                            <div style={{ color: 'var(--text-secondary)' }}>{v.vessel_type}</div>
                            <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Flag: {v.flag || 'Global'}</div>
                          </div>

                          <div style={{ fontFamily: 'monospace', color: 'var(--text-primary)' }}>
                            {v.points?.[0]?.speed_knots ? `${v.points[0].speed_knots} kts` : '12.0 kts'}
                          </div>

                          <div style={{ fontFamily: 'monospace', color: isFeasible ? 'var(--accent-cyan)' : 'var(--text-muted)' }}>
                            {feas ? `${dist} km` : '~22 km'}
                          </div>

                          <div>
                            {v.has_gap ? (
                              <span style={{
                                display: 'inline-flex',
                                alignItems: 'center',
                                gap: '4px',
                                color: '#d97706',
                                fontSize: '11px',
                                background: 'rgba(217, 119, 6, 0.12)',
                                padding: '2px 6px',
                                borderRadius: '4px'
                              }}>
                                <AlertTriangle size={11} /> 4h Silence
                              </span>
                            ) : (
                              <span style={{ color: 'var(--text-muted)', fontSize: '11px' }}>Continuous</span>
                            )}
                          </div>

                          <div>
                            {feas ? (
                              isFeasible ? (
                                <span style={{
                                  display: 'inline-flex',
                                  alignItems: 'center',
                                  gap: '4px',
                                  color: '#059669',
                                  fontSize: '11px',
                                  background: 'rgba(5, 150, 105, 0.12)',
                                  padding: '2px 8px',
                                  borderRadius: '6px',
                                  fontWeight: 600
                                }}>
                                  <CheckCircle2 size={12} /> Physically Feasible
                                </span>
                              ) : (
                                <span style={{
                                  display: 'inline-flex',
                                  alignItems: 'center',
                                  gap: '4px',
                                  color: '#e11d48',
                                  fontSize: '11px',
                                  background: 'rgba(225, 29, 72, 0.12)',
                                  padding: '2px 8px',
                                  borderRadius: '6px'
                                }}>
                                  <XCircle size={12} /> Excluded ({dist} km)
                                </span>
                              )
                            ) : (
                              <span style={{ color: 'var(--text-muted)', fontSize: '11px' }}>Track Active</span>
                            )}
                          </div>
                        </div>
                      );
                    })
                  )}
                </div>
              </div>

              {/* Vessel Detail Footnote */}
              {selectedVessel && (
                <div style={{
                  padding: '14px',
                  borderRadius: '10px',
                  background: 'var(--bg-tertiary)',
                  border: '1px solid var(--border-color)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between'
                }}>
                  <div>
                    <div style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text-primary)' }}>
                      Selected: {selectedVessel.vessel_name} ({selectedVessel.vessel_type})
                    </div>
                    <div style={{ fontSize: '11px', color: 'var(--text-secondary)', marginTop: '2px' }}>
                      {selectedVessel.points?.length || 0} discrete position points recorded across observation window.
                    </div>
                  </div>

                  <div style={{ display: 'flex', gap: '8px' }}>
                    <button
                      onClick={() => {
                        if (onAddCandidateToCase) {
                          onAddCandidateToCase(selectedVessel);
                          onClose();
                        }
                      }}
                      style={{
                        padding: '6px 12px',
                        borderRadius: '6px',
                        background: 'var(--accent-purple)',
                        color: '#fff',
                        border: 'none',
                        cursor: 'pointer',
                        fontSize: '12px',
                        fontWeight: 600,
                        display: 'flex',
                        alignItems: 'center',
                        gap: '6px'
                      }}
                    >
                      <ShieldAlert size={14} />
                      Set as Attribution Candidate
                    </button>
                  </div>
                </div>
              )}
            </>
          )}

          {activeTab === 'upload' && (
            <form onSubmit={handleFileUpload} style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
              <div style={{
                border: '2px dashed var(--border-color)',
                borderRadius: '12px',
                padding: '36px',
                textAlign: 'center',
                background: 'var(--bg-secondary)',
                cursor: 'pointer'
              }}>
                <FileText size={36} color="var(--accent-cyan)" style={{ margin: '0 auto 12px auto' }} />
                <div style={{ fontSize: '14px', fontWeight: 600, color: 'var(--text-primary)' }}>
                  Upload AIS NMEA 0183, CSV, or JSON Telemetry Log
                </div>
                <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '4px', maxWidth: '440px', margin: '4px auto 16px auto' }}>
                  Accepts raw <code>!AIVDM</code> sentences, MarineCadastre / EMSA CSV exports, or standard AISHub vessel lists.
                </div>
                <input
                  type="file"
                  accept=".nmea,.txt,.csv,.json"
                  onChange={(e) => setFileToUpload(e.target.files[0])}
                  style={{ fontSize: '12px', color: 'var(--text-secondary)' }}
                />
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px' }}>
                <button
                  type="submit"
                  disabled={!fileToUpload || loading}
                  style={{
                    padding: '8px 18px',
                    borderRadius: '8px',
                    background: fileToUpload ? 'var(--accent-cyan)' : 'var(--bg-tertiary)',
                    color: fileToUpload ? '#ffffff' : 'var(--text-muted)',
                    fontWeight: 600,
                    border: 'none',
                    cursor: fileToUpload ? 'pointer' : 'not-allowed',
                    fontSize: '13px',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '6px'
                  }}
                >
                  <Upload size={14} />
                  Parse & Ingest AIS Data
                </button>
              </div>

              {uploadResult && (
                <div style={{
                  padding: '14px',
                  borderRadius: '10px',
                  background: 'rgba(16, 185, 129, 0.1)',
                  border: '1px solid rgba(16, 185, 129, 0.3)',
                  color: 'var(--text-primary)',
                  fontSize: '12px'
                }}>
                  <div style={{ fontWeight: 600, color: '#10b981', display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <CheckCircle2 size={16} /> Ingestion Successful
                  </div>
                  <div style={{ marginTop: '4px', color: 'var(--text-secondary)' }}>
                    Processed file <strong>{uploadResult.filename}</strong>: parsed {uploadResult.vessels_parsed} vessels.
                  </div>
                </div>
              )}
            </form>
          )}
        </div>
      </div>
    </div>
  );
}
