import React, { useState, useEffect, useMemo } from 'react';
import { MapContainer, TileLayer, Polygon, Polyline, CircleMarker, Popup, useMap } from 'react-leaflet';
import { Layers, Eye, EyeOff, Navigation, Wind, Map as MapIcon } from 'lucide-react';

// Subcomponent to smoothly animate/recenter map on case change
function MapRecenter({ bounds }) {
  const map = useMap();
  useEffect(() => {
    if (bounds && bounds.length === 4) {
      const leafletBounds = [
        [bounds[1], bounds[0]], // [min_lat, min_lon]
        [bounds[3], bounds[2]]  // [max_lat, max_lon]
      ];
      map.fitBounds(leafletBounds, { padding: [40, 40], maxZoom: 12 });
    }
  }, [bounds, map]);
  return null;
}

export default function WebGISMap({
  caseData,
  selectedCandidate,
  visibleLayers,
  onToggleLayer
}) {
  const [basemapStyle, setBasemapStyle] = useState('light');
  const [metoceanData, setMetoceanData] = useState(null);

  useEffect(() => {
    if (!caseData?.fingerprint) return;
    const lat = caseData.fingerprint.centroid_lat;
    const lon = caseData.fingerprint.centroid_lon;
    fetch(`/api/v1/ais/metocean?lat=${lat}&lon=${lon}`)
      .then(res => res.ok ? res.json() : null)
      .then(data => { if (data) setMetoceanData(data); })
      .catch(() => {});
  }, [caseData]);

  if (!caseData) return null;

  const centerLat = caseData.fingerprint.centroid_lat;
  const centerLon = caseData.fingerprint.centroid_lon;

  // 1. Observed Spill Polygon Coordinates
  const spillCoords = useMemo(() => {
    const coords = caseData.spill_polygon.geometry.coordinates[0];
    return coords.map(([lon, lat]) => [lat, lon]);
  }, [caseData]);

  // 2. Origin Probability Polygon Coordinates
  const originCoords = useMemo(() => {
    if (!caseData.origin_field?.origin_polygon?.geometry?.coordinates) return [];
    const coords = caseData.origin_field.origin_polygon.geometry.coordinates[0];
    return coords.map(([lon, lat]) => [lat, lon]);
  }, [caseData]);

  // 3. Counterfactual Simulation Footprint Coordinates
  const counterfactualCoords = useMemo(() => {
    if (!selectedCandidate?.simulated_footprint?.geometry?.coordinates) return null;
    const coords = selectedCandidate.simulated_footprint.geometry.coordinates[0];
    return coords.map(([lon, lat]) => [lat, lon]);
  }, [selectedCandidate]);

  // 4. Forward Drift Trajectory Corridor Coordinates
  const forecastCoords = useMemo(() => {
    if (!caseData.forecast?.corridor_polygon?.geometry?.coordinates) return [];
    const coords = caseData.forecast.corridor_polygon.geometry.coordinates[0];
    return coords.map(([lon, lat]) => [lat, lon]);
  }, [caseData]);

  return (
    <div style={{ position: 'relative', width: '100%', height: '100%', overflow: 'hidden', borderRadius: '12px' }}>
      {/* Interactive Layer Toggle Controls Floating Bar */}
      <div style={{
        position: 'absolute',
        top: '14px',
        left: '14px',
        zIndex: 1000,
        background: 'rgba(255, 255, 255, 0.94)',
        backdropFilter: 'blur(10px)',
        border: '1px solid var(--border-color)',
        borderRadius: '10px',
        padding: '10px 14px',
        display: 'flex',
        flexDirection: 'column',
        gap: '8px',
        boxShadow: '0 4px 20px rgba(0,0,0,0.1)'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '11px', fontWeight: 700, color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
          <Layers size={14} color="var(--accent-cyan)" />
          <span>WebGIS Map Layers</span>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', fontSize: '12px' }}>
          <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer', color: visibleLayers.spill ? 'var(--text-primary)' : 'var(--text-muted)', fontWeight: visibleLayers.spill ? 600 : 400 }}>
            <input type="checkbox" checked={visibleLayers.spill} onChange={() => onToggleLayer('spill')} />
            <span style={{ display: 'inline-block', width: '10px', height: '10px', borderRadius: '2px', background: 'var(--spill-oil)' }} />
            Observed SAR Slick (Polygon)
          </label>

          <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer', color: visibleLayers.origin ? 'var(--text-primary)' : 'var(--text-muted)', fontWeight: visibleLayers.origin ? 600 : 400 }}>
            <input type="checkbox" checked={visibleLayers.origin} onChange={() => onToggleLayer('origin')} />
            <span style={{ display: 'inline-block', width: '10px', height: '10px', borderRadius: '2px', background: 'var(--origin-heat)' }} />
            Origin Probability Field
          </label>

          <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer', color: visibleLayers.ais ? 'var(--text-primary)' : 'var(--text-muted)', fontWeight: visibleLayers.ais ? 600 : 400 }}>
            <input type="checkbox" checked={visibleLayers.ais} onChange={() => onToggleLayer('ais')} />
            <span style={{ display: 'inline-block', width: '10px', height: '10px', borderRadius: '2px', background: 'var(--accent-cyan)' }} />
            AIS Candidate Vessel Tracks
          </label>

          <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer', color: visibleLayers.counterfactual ? 'var(--text-primary)' : 'var(--text-muted)', fontWeight: visibleLayers.counterfactual ? 600 : 400 }}>
            <input type="checkbox" checked={visibleLayers.counterfactual} onChange={() => onToggleLayer('counterfactual')} />
            <span style={{ display: 'inline-block', width: '10px', height: '10px', borderRadius: '2px', background: 'var(--accent-purple)' }} />
            Simulated Counterfactual Footprint
          </label>

          <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer', color: visibleLayers.forecast ? 'var(--text-primary)' : 'var(--text-muted)', fontWeight: visibleLayers.forecast ? 600 : 400 }}>
            <input type="checkbox" checked={visibleLayers.forecast} onChange={() => onToggleLayer('forecast')} />
            <span style={{ display: 'inline-block', width: '10px', height: '10px', borderRadius: '2px', background: 'var(--forecast-corridor)' }} />
            Forward Drift Corridor (24h)
          </label>

          <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer', color: visibleLayers.risk ? 'var(--text-primary)' : 'var(--text-muted)', fontWeight: visibleLayers.risk ? 600 : 400 }}>
            <input type="checkbox" checked={visibleLayers.risk} onChange={() => onToggleLayer('risk')} />
            <span style={{ display: 'inline-block', width: '10px', height: '10px', borderRadius: '2px', background: 'var(--vulnerability)' }} />
            Vulnerable Coastal Assets
          </label>
        </div>

        {/* Zero-API-Key Basemap Style Switcher */}
        <div style={{ height: '1px', background: 'var(--border-color)', margin: '4px 0 2px 0' }} />
        <div style={{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: '10px', fontWeight: 700, color: 'var(--text-secondary)', textTransform: 'uppercase' }}>
          <MapIcon size={12} color="var(--accent-cyan)" />
          <span>Basemap Style</span>
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr 1fr', gap: '4px' }}>
          {[
            { id: 'light', label: 'Light' },
            { id: 'osm', label: 'OSM' },
            { id: 'satellite', label: 'Sat' },
            { id: 'dark', label: 'Dark' }
          ].map((mode) => (
            <button
              key={mode.id}
              type="button"
              onClick={() => setBasemapStyle(mode.id)}
              style={{
                padding: '4px 2px',
                fontSize: '11px',
                borderRadius: '4px',
                border: basemapStyle === mode.id ? '1px solid var(--accent-cyan)' : '1px solid var(--border-color)',
                background: basemapStyle === mode.id ? 'rgba(2, 132, 199, 0.12)' : 'var(--bg-secondary)',
                color: basemapStyle === mode.id ? 'var(--accent-cyan)' : 'var(--text-muted)',
                cursor: 'pointer',
                fontWeight: basemapStyle === mode.id ? 700 : 400,
                textAlign: 'center'
              }}
            >
              {mode.label}
            </button>
          ))}
        </div>
      </div>

      {/* Environmental Forcing Telemetry Card */}
      <div style={{
        position: 'absolute',
        bottom: '20px',
        left: '14px',
        zIndex: 1000,
        background: 'rgba(255, 255, 255, 0.94)',
        backdropFilter: 'blur(8px)',
        border: '1px solid var(--border-color)',
        borderRadius: '8px',
        padding: '8px 12px',
        display: 'flex',
        alignItems: 'center',
        gap: '12px',
        fontSize: '11px',
        color: 'var(--text-secondary)',
        boxShadow: '0 4px 20px rgba(0,0,0,0.1)'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <Wind size={14} color="var(--accent-cyan)" />
          <span>10m Wind: <strong style={{ color: 'var(--text-primary)' }}>
            {metoceanData ? `${metoceanData.wind_speed_ms} m/s @ ${metoceanData.wind_dir_deg}°` : '7.8 m/s @ 220°'}
          </strong></span>
        </div>
        <div style={{ width: '1px', height: '14px', background: 'var(--border-color)' }} />
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <Navigation size={14} color="var(--accent-blue)" />
          <span>Ocean Current: <strong style={{ color: 'var(--text-primary)' }}>
            {metoceanData ? `${metoceanData.current_speed_ms} m/s @ ${metoceanData.current_dir_deg}°` : '0.38 m/s @ 205°'}
          </strong></span>
        </div>
        {metoceanData?.wave_height_m && (
          <>
            <div style={{ width: '1px', height: '14px', background: 'var(--border-color)' }} />
            <div style={{ color: 'var(--accent-emerald)', fontSize: '10px', fontWeight: 600 }}>
              Wave: {metoceanData.wave_height_m}m (Copernicus Live)
            </div>
          </>
        )}
      </div>

      {/* Leaflet Map Container */}
      <MapContainer
        center={[centerLat, centerLon]}
        zoom={9}
        scrollWheelZoom={true}
        style={{ width: '100%', height: '100%' }}
      >
        <MapRecenter bounds={caseData.aoi_bounds} />

        {/* Basemap TileLayers - Zero API Key Required */}
        {basemapStyle === 'light' && (
          <>
            <TileLayer
              key="light-base"
              url="https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Base/MapServer/tile/{z}/{y}/{x}"
              attribution='&copy; <a href="https://www.esri.com/">Esri</a>, DeLorme, NAVTEQ'
              maxZoom={16}
            />
            <TileLayer
              key="light-labels"
              url="https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Reference/MapServer/tile/{z}/{y}/{x}"
              attribution=""
              maxZoom={16}
            />
          </>
        )}

        {basemapStyle === 'dark' && (
          <>
            <TileLayer
              key="dark-base"
              url="https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}"
              attribution='&copy; <a href="https://www.esri.com/">Esri</a>, DeLorme, NAVTEQ'
              maxZoom={16}
            />
            <TileLayer
              key="dark-labels"
              url="https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Reference/MapServer/tile/{z}/{y}/{x}"
              attribution=""
              maxZoom={16}
            />
          </>
        )}

        {basemapStyle === 'satellite' && (
          <>
            <TileLayer
              key="sat-base"
              url="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
              attribution='&copy; <a href="https://www.esri.com/">Esri</a>, Maxar, Earthstar'
              maxZoom={18}
            />
            <TileLayer
              key="sat-labels"
              url="https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}"
              attribution=""
              maxZoom={18}
            />
          </>
        )}

        {basemapStyle === 'osm' && (
          <TileLayer
            key="osm-base"
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
            maxZoom={19}
          />
        )}

        {/* 1. Forward Drift Forecast Corridor */}
        {visibleLayers.forecast && forecastCoords.length > 0 && (
          <Polygon
            positions={forecastCoords}
            pathOptions={{
              color: '#3b82f6',
              weight: 2,
              fillColor: '#1d4ed8',
              fillOpacity: 0.18,
              dashArray: '4, 4'
            }}
          >
            <Popup>
              <strong>24-Hour Forward Drift Corridor</strong><br />
              Physics-based Lagrangian dispersion prediction envelope.
            </Popup>
          </Polygon>
        )}

        {/* 2. Origin Probability Field */}
        {visibleLayers.origin && originCoords.length > 0 && (
          <>
            <Polygon
              positions={originCoords}
              pathOptions={{
                color: '#f59e0b',
                weight: 2,
                fillColor: '#b45309',
                fillOpacity: 0.22,
                dashArray: '6, 6'
              }}
            >
              <Popup>
                <strong>Inferred Origin Probability Field</strong><br />
                Likely release window: {caseData.origin_field.release_window_start} to {caseData.origin_field.release_window_end}
              </Popup>
            </Polygon>

            {/* Heatmap Grid Points */}
            {caseData.origin_field.heatmap_grid?.map((pt, idx) => (
              <CircleMarker
                key={`heat_${idx}`}
                center={[pt.lat, pt.lon]}
                radius={8 * pt.density}
                pathOptions={{
                  stroke: false,
                  fillColor: '#f59e0b',
                  fillOpacity: pt.density * 0.5
                }}
              />
            ))}
          </>
        )}

        {/* 3. AIS Vessel Tracks */}
        {visibleLayers.ais && caseData.ais_tracks?.map((track) => {
          const latlngs = track.points.map(pt => [pt.lat, pt.lon]);
          const isSelected = selectedCandidate && selectedCandidate.mmsi === track.mmsi;
          const strokeColor = isSelected ? '#00e5ff' : '#64748b';
          const strokeWidth = isSelected ? 3.5 : 1.8;

          return (
            <React.Fragment key={track.mmsi}>
              <Polyline
                positions={latlngs}
                pathOptions={{
                  color: strokeColor,
                  weight: strokeWidth,
                  opacity: isSelected ? 1 : 0.65,
                  dashArray: track.has_gap ? '6, 6' : undefined
                }}
              >
                <Popup>
                  <strong>{track.vessel_name}</strong> ({track.vessel_type})<br />
                  MMSI: {track.mmsi} | Flag: {track.flag}<br />
                  {track.has_gap && <span style={{ color: '#f43f5e' }}>⚠️ AIS Gap Detected</span>}
                </Popup>
              </Polyline>

              {/* Waypoint markers */}
              {track.points.map((pt, pIdx) => (
                <CircleMarker
                  key={`${track.mmsi}_${pIdx}`}
                  center={[pt.lat, pt.lon]}
                  radius={isSelected ? 4.5 : 3}
                  pathOptions={{
                    color: isSelected ? '#00e5ff' : '#94a3b8',
                    fillColor: isSelected ? '#22d3ee' : '#475569',
                    fillOpacity: 0.9
                  }}
                >
                  <Popup>
                    {track.vessel_name} @ {pt.timestamp}<br />
                    Speed: {pt.speed_knots} kts | Heading: {pt.heading_deg}°
                  </Popup>
                </CircleMarker>
              ))}
            </React.Fragment>
          );
        })}

        {/* 4. Counterfactual Simulation Footprint */}
        {visibleLayers.counterfactual && counterfactualCoords && (
          <Polygon
            positions={counterfactualCoords}
            pathOptions={{
              color: '#c084fc',
              weight: 2.5,
              fillColor: '#9333ea',
              fillOpacity: 0.35,
              dashArray: '3, 3'
            }}
          >
            <Popup>
              <strong>Counterfactual Forward Simulation</strong><br />
              Candidate: {selectedCandidate.vessel_name}<br />
              Similarity Score: {selectedCandidate.counterfactual_score}%
            </Popup>
          </Polygon>
        )}

        {/* 5. Observed SAR Slick Polygon (Top Priority Visual) */}
        {visibleLayers.spill && spillCoords.length > 0 && (
          <Polygon
            positions={spillCoords}
            pathOptions={{
              color: '#f43f5e',
              weight: 2.5,
              fillColor: '#e11d48',
              fillOpacity: 0.55
            }}
          >
            <Popup>
              <strong>Observed Marine Oil Slick</strong><br />
              Sensor: {caseData.sensor}<br />
              Area: {caseData.fingerprint.area_km2} km²<br />
              Confidence: {(caseData.confirmation.overall_confidence * 100).toFixed(1)}%
            </Popup>
          </Polygon>
        )}

        {/* 6. Vulnerable Coastal Assets */}
        {visibleLayers.risk && caseData.vulnerable_assets?.map((asset) => {
          const coords = asset.geometry.geometry.coordinates[0].map(([lon, lat]) => [lat, lon]);
          return (
            <Polygon
              key={asset.asset_id}
              positions={coords}
              pathOptions={{
                color: '#ec4899',
                weight: 2,
                fillColor: '#db2777',
                fillOpacity: 0.3
              }}
            >
              <Popup>
                <strong>{asset.name}</strong><br />
                Type: {asset.asset_type}<br />
                Vulnerability: <span style={{ color: '#f43f5e', fontWeight: 700 }}>{asset.vulnerability_level}</span><br />
                Est. Impact in: {asset.estimated_impact_time_hours} hours
              </Popup>
            </Polygon>
          );
        })}
      </MapContainer>
    </div>
  );
}
