import React, { useState } from 'react';
import {
  Satellite, UploadCloud, CheckCircle2, AlertTriangle, RefreshCw,
  Sliders, MapPin, X, ArrowRight, ShieldAlert, Layers, Image as ImageIcon,
  Globe, Search, Radio, DownloadCloud, Sparkles
} from 'lucide-react';
import {
  uploadAndPredict,
  uploadCaseImage,
  searchCopernicusPasses,
  ingestCopernicusScene
} from '../services/api';

export default function AIDetectionModal({
  isOpen,
  onClose,
  caseId,
  currentLat = 28.6500,
  currentLon = -89.4200,
  onSpillDetected
}) {
  const [activeTab, setActiveTab] = useState('tile'); // 'tile' | 'copernicus'
  const [selectedFile, setSelectedFile] = useState(null);
  const [previewUrl, setPreviewUrl] = useState(null);
  const [threshold, setThreshold] = useState(0.25);
  const [centerLat, setCenterLat] = useState(currentLat);
  const [centerLon, setCenterLon] = useState(currentLon);
  const [kmSpan, setKmSpan] = useState(15.0);
  const [updateCase, setUpdateCase] = useState(true);
  const [isProcessing, setIsProcessing] = useState(false);
  const [predictionResult, setPredictionResult] = useState(null);
  const [errorMsg, setErrorMsg] = useState(null);

  // Copernicus Search & Ingest State
  const [copernicusProducts, setCopernicusProducts] = useState([]);
  const [isSearchingCopernicus, setIsSearchingCopernicus] = useState(false);
  const [ingestingProductId, setIngestingProductId] = useState(null);

  if (!isOpen) return null;

  const handleFileChange = (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setSelectedFile(file);
    setErrorMsg(null);
    setPredictionResult(null);

    if (file.name.endsWith('.npy')) {
      setPreviewUrl(null);
    } else {
      setPreviewUrl(URL.createObjectURL(file));
    }
  };

  const handleLoadSampleTile = async () => {
    try {
      setErrorMsg(null);
      setIsProcessing(true);
      const res = await fetch('/sample_sar_tile.png');
      const blob = await res.blob();
      const file = new File([blob], 'sentinel1_sample_tile.png', { type: 'image/png' });
      setSelectedFile(file);
      setPreviewUrl('/sample_sar_tile.png');
      setIsProcessing(false);
    } catch (err) {
      setErrorMsg('Failed to load preset sample tile: ' + err.message);
      setIsProcessing(false);
    }
  };

  const handleRunInference = async () => {
    if (!selectedFile) {
      setErrorMsg('Please select or load a SAR tile file first.');
      return;
    }

    setIsProcessing(true);
    setErrorMsg(null);

    try {
      if (updateCase && caseId) {
        // Upload directly into the active case
        const caseUploadRes = await uploadCaseImage(caseId, selectedFile, threshold);
        setPredictionResult(caseUploadRes.result);
        if (onSpillDetected && caseUploadRes.result) {
          onSpillDetected(caseUploadRes.result);
        }
      } else {
        // Run standalone prediction
        const result = await uploadAndPredict(selectedFile, {
          threshold,
          centerLat: parseFloat(centerLat),
          centerLon: parseFloat(centerLon),
          kmSpan: parseFloat(kmSpan)
        });
        setPredictionResult(result);
        if (onSpillDetected && result.oil_spill_detected) {
          onSpillDetected(result);
        }
      }
    } catch (err) {
      setErrorMsg(err.message || 'Detection failed. Ensure backend server is running.');
    } finally {
      setIsProcessing(false);
    }
  };

  const handleSearchCopernicus = async () => {
    try {
      setErrorMsg(null);
      setIsSearchingCopernicus(true);
      const cLat = parseFloat(centerLat) || 28.6500;
      const cLon = parseFloat(centerLon) || -89.4200;
      const bounds = {
        min_lon: cLon - 0.75,
        min_lat: cLat - 0.5,
        max_lon: cLon + 0.75,
        max_lat: cLat + 0.5,
      };
      const res = await searchCopernicusPasses(caseId, 6, bounds);
      setCopernicusProducts(res.products || []);
      if ((res.products || []).length === 0) {
        setErrorMsg('No Sentinel-1 GRD passes found for this maritime AOI.');
      }
    } catch (err) {
      setErrorMsg('Copernicus search failed: ' + err.message);
    } finally {
      setIsSearchingCopernicus(false);
    }
  };

  const handleIngestProduct = async (product) => {
    try {
      setErrorMsg(null);
      setIngestingProductId(product.product_id);
      const res = await ingestCopernicusScene(
        product.product_id,
        product.name,
        updateCase ? caseId : null,
        threshold,
        product.quicklook_url
      );
      setPredictionResult(res.detection);

      // Prefer locally served input tile URL to eliminate browser CORS/CORB blocks
      const localInput = res.input_tile_url || res.detection?.input_tile_url;
      if (localInput) {
        setPreviewUrl(localInput);
      } else if (product.quicklook_url && product.quicklook_url.startsWith('http')) {
        setPreviewUrl(product.quicklook_url);
      }

      if (onSpillDetected && res.detection?.oil_spill_detected) {
        onSpillDetected(res.detection);
      }
    } catch (err) {
      setErrorMsg('Copernicus ingestion failed: ' + err.message);
    } finally {
      setIngestingProductId(null);
    }
  };

  return (
    <div style={{
      position: 'fixed',
      top: 0,
      left: 0,
      right: 0,
      bottom: 0,
      background: 'rgba(15, 23, 42, 0.45)',
      backdropFilter: 'blur(10px)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      zIndex: 2000,
      padding: '24px'
    }}>
      <div className="glass-panel" style={{
        width: '940px',
        maxHeight: '90vh',
        display: 'flex',
        flexDirection: 'column',
        borderRadius: '16px',
        border: '1px solid var(--border-glow)',
        boxShadow: '0 25px 60px rgba(0, 0, 0, 0.15)',
        overflow: 'hidden',
        background: 'var(--bg-card)'
      }}>
        {/* Modal Header */}
        <div style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '16px 24px',
          borderBottom: '1px solid var(--border-color)',
          background: 'var(--bg-secondary)'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <div style={{
              width: '38px',
              height: '38px',
              borderRadius: '8px',
              background: 'linear-gradient(135deg, rgba(0, 229, 255, 0.2), rgba(168, 85, 247, 0.3))',
              border: '1px solid var(--border-glow)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center'
            }}>
              <Satellite size={20} color="var(--accent-cyan)" />
            </div>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <h2 style={{ fontSize: '16px', fontWeight: 800, color: 'var(--text-primary)' }}>
                  Satellite SAR AI Slick Detection
                </h2>
                <span className="badge badge-cyan" style={{ fontSize: '10px' }}>U-Net SAR</span>
              </div>
              <p style={{ fontSize: '11px', color: 'var(--text-secondary)', marginTop: '2px' }}>
                PyTorch SARUNet Baseline & Polygonizer (WGS84 GeoJSON + Geometric Fingerprinting)
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            style={{
              background: 'transparent',
              border: 'none',
              color: 'var(--text-secondary)',
              cursor: 'pointer',
              padding: '6px',
              borderRadius: '6px'
            }}
          >
            <X size={20} />
          </button>
        </div>

        {/* Tab Navigation */}
        <div style={{
          display: 'flex',
          borderBottom: '1px solid var(--border-color)',
          background: 'var(--bg-secondary)',
          padding: '0 24px',
          gap: '8px'
        }}>
          <button
            type="button"
            onClick={() => setActiveTab('tile')}
            style={{
              padding: '10px 16px',
              fontSize: '12px',
              fontWeight: 600,
              background: 'transparent',
              border: 'none',
              borderBottom: activeTab === 'tile' ? '2px solid var(--accent-cyan)' : '2px solid transparent',
              color: activeTab === 'tile' ? 'var(--accent-cyan)' : 'var(--text-secondary)',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '8px'
            }}
          >
            <Satellite size={15} />
            <span>SAR Tile Detection (Real Sentinel-1 / Upload)</span>
          </button>

          <button
            type="button"
            onClick={() => {
              setActiveTab('copernicus');
              if (copernicusProducts.length === 0) {
                handleSearchCopernicus();
              }
            }}
            style={{
              padding: '10px 16px',
              fontSize: '12px',
              fontWeight: 600,
              background: 'transparent',
              border: 'none',
              borderBottom: activeTab === 'copernicus' ? '2px solid var(--accent-cyan)' : '2px solid transparent',
              color: activeTab === 'copernicus' ? 'var(--accent-cyan)' : 'var(--text-secondary)',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '8px'
            }}
          >
            <Globe size={15} />
            <span>Copernicus CDSE Live Ingestion (Automated Search)</span>
            <span className="badge badge-purple" style={{ fontSize: '9px', padding: '1px 5px' }}>LIVE</span>
          </button>
        </div>

        {/* Modal Body */}
        <div style={{
          flex: 1,
          display: 'grid',
          gridTemplateColumns: '400px 1fr',
          overflowY: 'auto',
          padding: '20px 24px',
          gap: '20px'
        }}>
          {/* Left Column: Upload & Parameters OR Copernicus Search */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            {activeTab === 'copernicus' ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                <div style={{
                  padding: '12px',
                  borderRadius: '10px',
                  background: 'rgba(168, 85, 247, 0.08)',
                  border: '1px solid rgba(168, 85, 247, 0.25)',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '6px'
                }}>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <span style={{ fontSize: '12px', fontWeight: 700, color: '#fff' }}>Copernicus Data Space (CDSE)</span>
                      <span style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', fontSize: '9px', fontWeight: 700, color: 'var(--accent-emerald)', background: 'rgba(16, 185, 129, 0.15)', padding: '2px 6px', borderRadius: '4px' }}>
                        ● ONLINE
                      </span>
                    </div>
                    <button
                      type="button"
                      onClick={handleSearchCopernicus}
                      disabled={isSearchingCopernicus}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: '4px',
                        background: 'rgba(168, 85, 247, 0.2)',
                        border: '1px solid var(--accent-purple)',
                        color: '#fff',
                        fontSize: '11px',
                        padding: '4px 8px',
                        borderRadius: '6px',
                        cursor: isSearchingCopernicus ? 'not-allowed' : 'pointer'
                      }}
                    >
                      <RefreshCw size={12} className={isSearchingCopernicus ? 'spin' : ''} />
                      {isSearchingCopernicus ? 'Searching...' : 'Refresh Passes'}
                    </button>
                  </div>
                  <p style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>
                    Queries live Sentinel-1 C-SAR GRD acquisitions intersecting <strong>{caseId || 'AOI'}</strong>.
                  </p>
                </div>

                {/* Products List */}
                <div style={{
                  maxHeight: '280px',
                  overflowY: 'auto',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '8px'
                }}>
                  {copernicusProducts.map((p) => {
                    const isIngesting = ingestingProductId === p.product_id;
                    return (
                      <div
                        key={p.product_id}
                        className="glass-panel"
                        style={{
                          padding: '10px 12px',
                          borderRadius: '8px',
                          border: isIngesting ? '1px solid var(--accent-cyan)' : '1px solid var(--border-color)',
                          background: 'rgba(7, 13, 24, 0.6)'
                        }}
                      >
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '8px' }}>
                          <div style={{ fontSize: '11px', fontWeight: 700, color: '#fff', wordBreak: 'break-all' }}>
                            {p.name}
                          </div>
                          <span className={p.is_live_cdse ? 'badge badge-emerald' : 'badge badge-purple'} style={{ fontSize: '8px', whiteSpace: 'nowrap', padding: '1px 4px' }}>
                            {p.is_live_cdse ? 'LIVE ODATA' : 'CATALOG'}
                          </span>
                        </div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '10px', color: 'var(--text-secondary)', marginTop: '4px' }}>
                          <span>⏱️ {p.acquisition_time ? p.acquisition_time.split('T')[0] : 'Recent'}</span>
                          <span>🛰️ {p.mode || 'IW'}</span>
                          <span>📶 {p.polarization}</span>
                        </div>
                        <div style={{ marginTop: '8px', display: 'flex', justifyContent: 'flex-end' }}>
                          <button
                            type="button"
                            onClick={() => handleIngestProduct(p)}
                            disabled={isIngesting}
                            style={{
                              display: 'flex',
                              alignItems: 'center',
                              gap: '6px',
                              padding: '5px 10px',
                              fontSize: '11px',
                              fontWeight: 600,
                              borderRadius: '6px',
                              border: 'none',
                              background: isIngesting ? 'var(--bg-tertiary)' : 'linear-gradient(135deg, #00e5ff, #a855f7)',
                              color: '#070d18',
                              cursor: isIngesting ? 'not-allowed' : 'pointer'
                            }}
                          >
                            <Sparkles size={12} />
                            {isIngesting ? 'Ingesting & Detecting...' : 'Ingest & Detect (U-Net)'}
                          </button>
                        </div>
                      </div>
                    );
                  })}
                  {copernicusProducts.length === 0 && !isSearchingCopernicus && (
                    <div style={{ textAlign: 'center', padding: '24px 12px', color: 'var(--text-muted)', fontSize: '12px' }}>
                      Click 'Refresh Passes' to discover live satellite passes.
                    </div>
                  )}
                </div>
              </div>
            ) : (
              <>
                {/* Upload Box */}
                <div style={{
                  border: '2px dashed var(--border-color)',
                  borderRadius: '12px',
                  padding: '20px',
                  textAlign: 'center',
                  background: 'rgba(10, 20, 38, 0.4)',
                  cursor: 'pointer',
                  transition: 'all 0.2s ease',
                  position: 'relative'
                }}>
                  <input
                    type="file"
                    accept=".png,.jpg,.jpeg,.tif,.tiff,.npy"
                    onChange={handleFileChange}
                    style={{
                      position: 'absolute',
                      top: 0,
                      left: 0,
                      width: '100%',
                      height: '100%',
                      opacity: 0,
                      cursor: 'pointer'
                    }}
                  />
                  <UploadCloud size={32} color="var(--accent-cyan)" style={{ margin: '0 auto 8px auto' }} />
                  <p style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text-primary)' }}>
                    {selectedFile ? selectedFile.name : 'Select or drop SAR Tile'}
                  </p>
                  <p style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '4px' }}>
                    Supports Sentinel-1 SAR (.png, .jpg, .npy, .tif)
                  </p>
                </div>

                {/* Quick Sample Loader */}
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>Real SAR data?</span>
                  <button
                    type="button"
                    onClick={handleLoadSampleTile}
                    style={{
                      background: 'rgba(0, 229, 255, 0.12)',
                      border: '1px solid var(--accent-cyan)',
                      color: 'var(--accent-cyan)',
                      padding: '4px 10px',
                      borderRadius: '6px',
                      fontSize: '11px',
                      fontWeight: 600,
                      cursor: 'pointer'
                    }}
                  >
                    Load Real Sentinel-1 Tile
                  </button>
                </div>
              </>
            )}

            {/* Detection Threshold */}
            <div className="glass-panel" style={{ padding: '12px 14px', borderRadius: '10px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '6px' }}>
                <span style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-secondary)' }}>
                  Slick Confidence Threshold
                </span>
                <span style={{ fontSize: '12px', fontWeight: 700, color: 'var(--accent-cyan)' }}>
                  {(threshold * 100).toFixed(0)}%
                </span>
              </div>
              <input
                type="range"
                min="0.10"
                max="0.90"
                step="0.05"
                value={threshold}
                onChange={(e) => setThreshold(parseFloat(e.target.value))}
                style={{ width: '100%', accentColor: 'var(--accent-cyan)', cursor: 'pointer' }}
              />
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '10px', color: 'var(--text-muted)', marginTop: '4px' }}>
                <span>10% (High Recall)</span>
                <span>50% (Standard)</span>
                <span>90% (High Precision)</span>
              </div>
            </div>

            {/* Geographic Coordinates */}
            <div className="glass-panel" style={{ padding: '12px 14px', borderRadius: '10px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '8px' }}>
                <MapPin size={14} color="var(--accent-cyan)" />
                <span style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-primary)' }}>
                  Tile Geographic Anchoring (WGS84)
                </span>
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
                <div>
                  <label style={{ fontSize: '10px', color: 'var(--text-secondary)' }}>Center Latitude</label>
                  <input
                    type="number"
                    step="0.0001"
                    value={centerLat}
                    onChange={(e) => setCenterLat(e.target.value)}
                    style={{
                      width: '100%',
                      background: 'var(--bg-card)',
                      border: '1px solid var(--border-color)',
                      borderRadius: '6px',
                      padding: '6px 8px',
                      color: 'var(--text-primary)',
                      fontSize: '12px',
                      marginTop: '2px'
                    }}
                  />
                </div>
                <div>
                  <label style={{ fontSize: '10px', color: 'var(--text-secondary)' }}>Center Longitude</label>
                  <input
                    type="number"
                    step="0.0001"
                    value={centerLon}
                    onChange={(e) => setCenterLon(e.target.value)}
                    style={{
                      width: '100%',
                      background: 'var(--bg-card)',
                      border: '1px solid var(--border-color)',
                      borderRadius: '6px',
                      padding: '6px 8px',
                      color: 'var(--text-primary)',
                      fontSize: '12px',
                      marginTop: '2px'
                    }}
                  />
                </div>
              </div>
            </div>

            {/* Target Case Toggle */}
            <label style={{
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              fontSize: '12px',
              color: 'var(--text-secondary)',
              cursor: 'pointer'
            }}>
              <input
                type="checkbox"
                checked={updateCase}
                onChange={(e) => setUpdateCase(e.target.checked)}
                style={{ accentColor: 'var(--accent-cyan)' }}
              />
              Update active investigation case ({caseId}) with detected slick
            </label>

            {/* Error Message */}
            {errorMsg && (
              <div style={{
                background: 'rgba(244, 63, 94, 0.15)',
                border: '1px solid var(--accent-rose)',
                borderRadius: '8px',
                padding: '8px 12px',
                fontSize: '12px',
                color: 'var(--accent-rose)'
              }}>
                {errorMsg}
              </div>
            )}

            {/* Run Button */}
            <button
              onClick={handleRunInference}
              disabled={isProcessing || !selectedFile}
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: '8px',
                background: isProcessing ? 'var(--bg-tertiary)' : 'linear-gradient(135deg, #00e5ff, #0077b6)',
                color: isProcessing ? 'var(--text-secondary)' : '#ffffff',
                fontWeight: 700,
                fontSize: '13px',
                border: 'none',
                borderRadius: '8px',
                padding: '12px 16px',
                cursor: (isProcessing || !selectedFile) ? 'not-allowed' : 'pointer',
                transition: 'all 0.2s ease',
                boxShadow: (isProcessing || !selectedFile) ? 'none' : '0 0 20px rgba(0, 229, 255, 0.4)'
              }}
            >
              <RefreshCw size={16} className={isProcessing ? 'spin' : ''} />
              {isProcessing ? 'Analyzing Microwave Backscatter...' : 'Run SAR U-Net Detection'}
            </button>
          </div>

          {/* Right Column: Visualization & Detection Results */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
            {/* Visual Viewport */}
            <div style={{
              display: 'grid',
              gridTemplateColumns: '1fr 1fr',
              gap: '12px',
              minHeight: '220px'
            }}>
              {/* Input Preview */}
              <div className="glass-panel" style={{
                borderRadius: '10px',
                overflow: 'hidden',
                display: 'flex',
                flexDirection: 'column'
              }}>
                <div style={{
                  padding: '6px 10px',
                  background: 'var(--bg-tertiary)',
                  fontSize: '11px',
                  fontWeight: 600,
                  color: 'var(--text-secondary)'
                }}>
                  Input Satellite Tile
                </div>
                <div style={{
                  flex: 1,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  background: 'var(--bg-secondary)',
                  padding: '8px'
                }}>
                  {previewUrl ? (
                    <img
                      src={previewUrl}
                      alt="Raw Input Tile"
                      style={{ maxWidth: '100%', maxHeight: '180px', objectFit: 'contain', borderRadius: '6px' }}
                    />
                  ) : (
                    <div style={{ textAlign: 'center', color: 'var(--text-muted)', fontSize: '11px' }}>
                      <ImageIcon size={28} style={{ margin: '0 auto 6px auto', opacity: 0.4 }} />
                      <span>{selectedFile ? 'NumPy .npy format (Ready for inference)' : 'No image selected'}</span>
                    </div>
                  )}
                </div>
              </div>

              {/* AI Segmentation Overlay */}
              <div className="glass-panel" style={{
                borderRadius: '10px',
                overflow: 'hidden',
                display: 'flex',
                flexDirection: 'column'
              }}>
                <div style={{
                  padding: '6px 10px',
                  background: 'var(--bg-tertiary)',
                  fontSize: '11px',
                  fontWeight: 600,
                  color: 'var(--text-secondary)'
                }}>
                  AI Detection Mask & Overlay
                </div>
                <div style={{
                  flex: 1,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  background: 'var(--bg-secondary)',
                  padding: '8px'
                }}>
                  {predictionResult?.overlay_url ? (
                    <img
                      src={predictionResult.overlay_url}
                      alt="AI Segmentation Overlay"
                      style={{ maxWidth: '100%', maxHeight: '180px', objectFit: 'contain', borderRadius: '6px' }}
                    />
                  ) : (
                    <div style={{ textAlign: 'center', color: 'var(--text-muted)', fontSize: '11px' }}>
                      <Layers size={28} style={{ margin: '0 auto 6px auto', opacity: 0.4 }} />
                      <span>Run inference to generate segmentation mask</span>
                    </div>
                  )}
                </div>
              </div>
            </div>

            {/* Inference Outcome */}
            {predictionResult ? (
              <div className="glass-panel" style={{
                padding: '16px',
                borderRadius: '12px',
                border: predictionResult.oil_spill_detected
                  ? '1px solid rgba(244, 63, 94, 0.5)'
                  : '1px solid rgba(16, 185, 129, 0.5)'
              }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '12px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    {predictionResult.oil_spill_detected ? (
                      <ShieldAlert size={20} color="var(--accent-rose)" />
                    ) : (
                      <CheckCircle2 size={20} color="var(--accent-emerald)" />
                    )}
                    <span style={{
                      fontSize: '14px',
                      fontWeight: 800,
                      color: predictionResult.oil_spill_detected ? 'var(--accent-rose)' : 'var(--accent-emerald)'
                    }}>
                      {predictionResult.oil_spill_detected ? 'OIL SPILL CONFIRMED' : 'NO SPILL / LOOK-ALIKE'}
                    </span>
                  </div>
                  <span className="badge badge-cyan" style={{ fontSize: '11px' }}>
                    Confidence: {(predictionResult.confidence * 100).toFixed(1)}%
                  </span>
                </div>

                {/* Metrics Grid */}
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '8px', marginBottom: '12px' }}>
                  <div style={{ background: 'var(--bg-secondary)', padding: '8px', borderRadius: '6px' }}>
                    <div style={{ fontSize: '10px', color: 'var(--text-secondary)' }}>Slick Pixels</div>
                    <div style={{ fontSize: '14px', fontWeight: 700, color: 'var(--text-primary)' }}>
                      {predictionResult.spill_area_pixels?.toLocaleString() || 0}
                    </div>
                  </div>
                  <div style={{ background: 'var(--bg-secondary)', padding: '8px', borderRadius: '6px' }}>
                    <div style={{ fontSize: '10px', color: 'var(--text-secondary)' }}>Pixel Ratio</div>
                    <div style={{ fontSize: '14px', fontWeight: 700, color: 'var(--accent-cyan)' }}>
                      {((predictionResult.spill_ratio || 0) * 100).toFixed(2)}%
                    </div>
                  </div>
                  <div style={{ background: 'var(--bg-secondary)', padding: '8px', borderRadius: '6px' }}>
                    <div style={{ fontSize: '10px', color: 'var(--text-secondary)' }}>Est. Area</div>
                    <div style={{ fontSize: '14px', fontWeight: 700, color: 'var(--accent-amber)' }}>
                      {predictionResult.fingerprint?.area_km2
                        ? `${predictionResult.fingerprint.area_km2.toFixed(2)} km²`
                        : 'N/A'}
                    </div>
                  </div>
                  <div style={{ background: 'var(--bg-secondary)', padding: '8px', borderRadius: '6px' }}>
                    <div style={{ fontSize: '10px', color: 'var(--text-secondary)' }}>Aspect Ratio</div>
                    <div style={{ fontSize: '14px', fontWeight: 700, color: 'var(--accent-purple)' }}>
                      {predictionResult.fingerprint?.aspect_ratio
                        ? predictionResult.fingerprint.aspect_ratio.toFixed(2)
                        : 'N/A'}
                    </div>
                  </div>
                </div>

                {/* Fingerprint Data Snippet */}
                {predictionResult.fingerprint && (
                  <div style={{
                    fontSize: '11px',
                    color: 'var(--text-secondary)',
                    background: 'var(--bg-secondary)',
                    padding: '8px 12px',
                    borderRadius: '6px',
                    display: 'flex',
                    justifyContent: 'space-between'
                  }}>
                    <span>Perimeter: {predictionResult.fingerprint.perimeter_km?.toFixed(2)} km</span>
                    <span>Compactness: {predictionResult.fingerprint.compactness?.toFixed(3)}</span>
                    <span>Orientation: {predictionResult.fingerprint.orientation_deg?.toFixed(1)}°</span>
                  </div>
                )}
              </div>
            ) : (
              <div className="glass-panel" style={{
                flex: 1,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                borderRadius: '12px',
                padding: '24px',
                textAlign: 'center'
              }}>
                <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
                  Upload a satellite SAR tile and click "Run SAR U-Net Detection" to extract segmentation masks,
                  GeoJSON coordinates, and morphological fingerprints.
                </span>
              </div>
            )}
          </div>
        </div>

        {/* Modal Footer */}
        <div style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'flex-end',
          gap: '10px',
          padding: '12px 24px',
          borderTop: '1px solid var(--border-color)',
          background: 'var(--bg-secondary)'
        }}>
          <button
            onClick={onClose}
            style={{
              background: 'var(--bg-tertiary)',
              color: 'var(--text-primary)',
              border: '1px solid var(--border-color)',
              borderRadius: '8px',
              padding: '8px 16px',
              fontSize: '12px',
              fontWeight: 600,
              cursor: 'pointer'
            }}
          >
            Close
          </button>
          {predictionResult?.oil_spill_detected && (
            <button
              onClick={() => {
                if (onSpillDetected) onSpillDetected(predictionResult);
                onClose();
              }}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                background: 'linear-gradient(135deg, #00e5ff, #0077b6)',
                color: '#ffffff',
                border: 'none',
                borderRadius: '8px',
                padding: '8px 16px',
                fontSize: '12px',
                fontWeight: 700,
                cursor: 'pointer'
              }}
            >
              Apply to WebGIS Map <ArrowRight size={14} />
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
