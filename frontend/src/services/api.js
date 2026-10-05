const API_BASE = '/api/v1';

export async function fetchCasesList() {
  try {
    const res = await fetch(`${API_BASE}/cases`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  } catch (err) {
    console.warn('Backend fetch failed, using fallback list:', err);
    return [
      {
        case_id: "GOM-2024-0418",
        title: "Mississippi Canyon / Barataria Drift Slick",
        region: "Gulf of Mexico (Offshore Louisiana)",
        observation_time: "2024-04-18T05:32:00 UTC",
        sensor: "Sentinel-1 SAR (C-Band VV)",
        status: "COMPLETED",
        spill_area_km2: 18.42,
        top_candidate: "MT Starlight Spirit",
        top_score: 93.4
      },
      {
        case_id: "MUM-2024-0512",
        title: "Mumbai High Offshore Approach Spill",
        region: "Arabian Sea (West Coast of India)",
        observation_time: "2024-05-12T12:18:00 UTC",
        sensor: "Sentinel-1 SAR",
        status: "COMPLETED",
        spill_area_km2: 12.85,
        top_candidate: "MT Samudra Ratna",
        top_score: 91.2
      }
    ];
  }
}

export async function fetchCaseDetails(caseId) {
  try {
    const res = await fetch(`${API_BASE}/cases/${caseId}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  } catch (err) {
    console.error(`Error fetching case ${caseId}:`, err);
    return null;
  }
}

export async function fetchCaseReport(caseId) {
  try {
    const res = await fetch(`${API_BASE}/cases/${caseId}/report`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  } catch (err) {
    console.error(`Error fetching report for ${caseId}:`, err);
    return { case_id: caseId, report_markdown: "# Error loading report from server." };
  }
}

export async function runBacktrack(caseId, params = {}) {
  const q = new URLSearchParams();
  if (params.maxHindcastHours) q.append('max_hindcast_hours', params.maxHindcastHours);
  if (params.windSpeedMs) q.append('wind_speed_ms', params.windSpeedMs);
  if (params.currentSpeedMs) q.append('current_speed_ms', params.currentSpeedMs);

  const res = await fetch(`${API_BASE}/cases/${caseId}/backtrack?${q}`, { method: 'POST' });
  if (!res.ok) throw new Error(`Backtrack failed: HTTP ${res.status}`);
  return await res.json();
}

export async function runCounterfactual(caseId, releaseHoursAgo = 18.0) {
  const q = new URLSearchParams({ release_hours_ago: releaseHoursAgo.toString() });
  const res = await fetch(`${API_BASE}/cases/${caseId}/counterfactual?${q}`, { method: 'POST' });
  if (!res.ok) throw new Error(`Counterfactual failed: HTTP ${res.status}`);
  return await res.json();
}

export async function runForecast(caseId, forecastHorizonHours = 24) {
  const q = new URLSearchParams({ forecast_horizon_hours: forecastHorizonHours.toString() });
  const res = await fetch(`${API_BASE}/cases/${caseId}/forecast?${q}`, { method: 'POST' });
  if (!res.ok) throw new Error(`Forecast failed: HTTP ${res.status}`);
  return await res.json();
}

export async function runRiskAssessment(caseId) {
  const res = await fetch(`${API_BASE}/cases/${caseId}/risk`, { method: 'POST' });
  if (!res.ok) throw new Error(`Risk assessment failed: HTTP ${res.status}`);
  return await res.json();
}

export async function persistCaseToDb(caseId) {
  const res = await fetch(`${API_BASE}/cases/${caseId}/persist`, { method: 'POST' });
  if (!res.ok) throw new Error(`Persistence failed: HTTP ${res.status}`);
  return await res.json();
}

export async function uploadAndPredict(file, { threshold = 0.5, centerLat = 28.65, centerLon = -89.42, kmSpan = 15.0 } = {}) {
  const formData = new FormData();
  formData.append('file', file);
  const params = new URLSearchParams({
    threshold: threshold.toString(),
    center_lat: centerLat.toString(),
    center_lon: centerLon.toString(),
    km_span: kmSpan.toString(),
  });

  const res = await fetch(`${API_BASE}/predict?${params}`, {
    method: 'POST',
    body: formData,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: `HTTP ${res.status}` }));
    throw new Error(err.detail || 'Prediction failed');
  }
  return await res.json();
}

export async function uploadCaseImage(caseId, file, threshold = 0.5) {
  const formData = new FormData();
  formData.append('file', file);
  const params = new URLSearchParams({ threshold: threshold.toString() });

  const res = await fetch(`${API_BASE}/cases/${caseId}/detect_upload?${params}`, {
    method: 'POST',
    body: formData,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: `HTTP ${res.status}` }));
    throw new Error(err.detail || 'Case detection upload failed');
  }
  return await res.json();
}

export async function searchCopernicusPasses(caseId, limit = 6, bounds = null) {
  const params = new URLSearchParams();
  if (caseId) params.append('case_id', caseId);
  params.append('limit', limit.toString());
  if (bounds) {
    if (bounds.min_lon !== undefined && bounds.min_lon !== null) params.append('min_lon', bounds.min_lon.toString());
    if (bounds.min_lat !== undefined && bounds.min_lat !== null) params.append('min_lat', bounds.min_lat.toString());
    if (bounds.max_lon !== undefined && bounds.max_lon !== null) params.append('max_lon', bounds.max_lon.toString());
    if (bounds.max_lat !== undefined && bounds.max_lat !== null) params.append('max_lat', bounds.max_lat.toString());
  }

  const res = await fetch(`${API_BASE}/copernicus/search?${params}`);
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: `HTTP ${res.status}` }));
    throw new Error(err.detail || 'Copernicus search failed');
  }
  return await res.json();
}

export async function ingestCopernicusScene(productId, productName, caseId = null, threshold = 0.5, quicklookUrl = null) {
  const params = new URLSearchParams({
    product_id: productId,
    product_name: productName,
    threshold: threshold.toString(),
  });
  if (caseId) params.append('case_id', caseId);
  if (quicklookUrl) params.append('quicklook_url', quicklookUrl);

  const res = await fetch(`${API_BASE}/copernicus/ingest-and-detect?${params}`, {
    method: 'POST',
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: `HTTP ${res.status}` }));
    throw new Error(err.detail || 'Copernicus ingestion failed');
  }
  return await res.json();
}
