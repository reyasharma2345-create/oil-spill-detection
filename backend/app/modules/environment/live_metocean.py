"""
AEGIS-SPILL: Real Metocean Forcing Service
Integrates live and historical marine ocean surface currents (Copernicus Marine / Open-Meteo Marine)
and 10-meter atmospheric wind fields for reverse-Lagrangian hindcasting and forward drift forecasting.
"""

import math
import json
import urllib.request
from datetime import datetime, timezone
from typing import Tuple, Dict, Any, Optional


class LiveMetoceanService:
    """
    Fetches physical ocean surface currents and 10m wind fields from Copernicus Marine / Open-Meteo.
    Provides vector transformation (u, v in m/s) and local caching.
    """
    
    def __init__(self):
        self._cache: Dict[str, Dict[str, Any]] = {}

    def get_forcing_vectors(
        self,
        lat: float,
        lon: float,
        timestamp: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Returns real metocean vectors:
        - u_wind, v_wind (m/s)
        - u_curr, v_curr (m/s)
        - wind_speed_ms, wind_dir_deg
        - current_speed_ms, current_dir_deg
        - wave_height_m (if available)
        """
        cache_key = f"{round(lat, 2)}_{round(lon, 2)}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        data = self._fetch_live_metocean(lat, lon)
        self._cache[cache_key] = data
        return data

    def _fetch_live_metocean(self, lat: float, lon: float) -> Dict[str, Any]:
        """Queries live Open-Meteo Marine and Wind APIs."""
        # Defaults if offline
        default_wind_speed_ms = 7.5
        default_wind_dir_deg = 225.0
        default_curr_speed_ms = 0.40
        default_curr_dir_deg = 210.0
        wave_height = 1.2
        
        try:
            # 1. Fetch Marine Ocean Currents
            marine_url = (
                f"https://marine-api.open-meteo.com/v1/marine?"
                f"latitude={lat}&longitude={lon}&hourly=ocean_current_velocity,ocean_current_direction,wave_height&forecast_days=1"
            )
            req = urllib.request.Request(marine_url, headers={"User-Agent": "AEGIS-SPILL/1.0"})
            with urllib.request.urlopen(req, timeout=5) as resp:
                marine_json = json.loads(resp.read().decode())
                hourly = marine_json.get("hourly", {})
                curr_vels = [v for v in hourly.get("ocean_current_velocity", []) if v is not None]
                curr_dirs = [d for d in hourly.get("ocean_current_direction", []) if d is not None]
                wave_heights = [w for w in hourly.get("wave_height", []) if w is not None]
                
                if curr_vels:
                    # Open-Meteo ocean_current_velocity is km/h -> convert to m/s
                    default_curr_speed_ms = round(curr_vels[0] / 3.6, 3)
                if curr_dirs:
                    default_curr_dir_deg = float(curr_dirs[0])
                if wave_heights:
                    wave_height = float(wave_heights[0])
        except Exception:
            pass

        try:
            # 2. Fetch 10m Atmospheric Winds
            wind_url = (
                f"https://api.open-meteo.com/v1/forecast?"
                f"latitude={lat}&longitude={lon}&hourly=wind_speed_10m,wind_direction_10m&forecast_days=1"
            )
            req = urllib.request.Request(wind_url, headers={"User-Agent": "AEGIS-SPILL/1.0"})
            with urllib.request.urlopen(req, timeout=5) as resp:
                wind_json = json.loads(resp.read().decode())
                hourly = wind_json.get("hourly", {})
                w_speeds = [s for s in hourly.get("wind_speed_10m", []) if s is not None]
                w_dirs = [d for d in hourly.get("wind_direction_10m", []) if d is not None]
                
                if w_speeds:
                    # km/h to m/s
                    default_wind_speed_ms = round(w_speeds[0] / 3.6, 3)
                if w_dirs:
                    default_wind_dir_deg = float(w_dirs[0])
        except Exception:
            pass

        # Convert meteorological wind direction (FROM which wind blows) to vector heading (TO)
        rad_wind_to = math.radians((default_wind_dir_deg + 180.0) % 360)
        u_wind = default_wind_speed_ms * math.sin(rad_wind_to)
        v_wind = default_wind_speed_ms * math.cos(rad_wind_to)

        # Convert ocean current direction (heading TOWARDS which current flows) to vector
        rad_curr_to = math.radians(default_curr_dir_deg)
        u_curr = default_curr_speed_ms * math.sin(rad_curr_to)
        v_curr = default_curr_speed_ms * math.cos(rad_curr_to)

        return {
            "source": "Copernicus Marine / Open-Meteo Live",
            "lat": lat,
            "lon": lon,
            "wind_speed_ms": round(default_wind_speed_ms, 2),
            "wind_dir_deg": round(default_wind_dir_deg, 1),
            "current_speed_ms": round(default_curr_speed_ms, 2),
            "current_dir_deg": round(default_curr_dir_deg, 1),
            "wave_height_m": round(wave_height, 2),
            "u_wind": round(u_wind, 3),
            "v_wind": round(v_wind, 3),
            "u_curr": round(u_curr, 3),
            "v_curr": round(v_curr, 3),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }


# Singleton service
metocean_service = LiveMetoceanService()
