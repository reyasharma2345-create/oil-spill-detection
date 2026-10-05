import math
import numpy as np
from typing import Tuple, Dict, Any

class EnvironmentalForcing:
    """
    Simulates or interpolates 2D spatially and temporally varying Wind (u_wind, v_wind)
    and Ocean Current (u_curr, v_curr) fields for transport modeling.
    """
    def __init__(self, mean_wind_speed_ms: float = 8.5, wind_dir_deg: float = 225.0,
                 mean_current_speed_ms: float = 0.45, current_dir_deg: float = 210.0):
        # Convert meteorological direction (from) to vector heading (to)
        rad_wind = math.radians((90 - wind_dir_deg) % 360)
        self.u_wind_base = mean_wind_speed_ms * math.cos(rad_wind)
        self.v_wind_base = mean_wind_speed_ms * math.sin(rad_wind)
        
        rad_curr = math.radians((90 - current_dir_deg) % 360)
        self.u_curr_base = mean_current_speed_ms * math.cos(rad_curr)
        self.v_curr_base = mean_current_speed_ms * math.sin(rad_curr)

    def get_forcing_at(self, lat: float, lon: float, time_offset_hours: float) -> Tuple[float, float, float, float]:
        """
        Returns (u_wind, v_wind, u_curr, v_curr) in m/s with mild spatial/temporal turbulence.
        """
        # Small spatial variation based on lat/lon
        spatial_factor_wind = 1.0 + 0.05 * math.sin(lat * 10) + 0.04 * math.cos(lon * 10)
        spatial_factor_curr = 1.0 + 0.08 * math.cos(lat * 8) + 0.06 * math.sin(lon * 8)
        
        # Temporal variation (semi-diurnal tide / wind shift simulation)
        temporal_wind = 1.0 + 0.10 * math.sin(time_offset_hours * math.pi / 6.0)
        temporal_curr = 1.0 + 0.15 * math.cos(time_offset_hours * math.pi / 6.0)
        
        u_w = self.u_wind_base * spatial_factor_wind * temporal_wind
        v_w = self.v_wind_base * spatial_factor_wind * temporal_wind
        
        u_c = self.u_curr_base * spatial_factor_curr * temporal_curr
        v_c = self.v_curr_base * spatial_factor_curr * temporal_curr
        
        return u_w, v_w, u_c, v_c


class LiveEnvironmentalForcing(EnvironmentalForcing):
    """
    Subclass that integrates live physical ocean surface current and wind vectors
    from Copernicus Marine / Open-Meteo.
    """
    def __init__(self, lat: float, lon: float):
        try:
            from app.modules.environment.live_metocean import metocean_service
            data = metocean_service.get_forcing_vectors(lat, lon)
            super().__init__(
                mean_wind_speed_ms=data["wind_speed_ms"],
                wind_dir_deg=data["wind_dir_deg"],
                mean_current_speed_ms=data["current_speed_ms"],
                current_dir_deg=data["current_dir_deg"]
            )
            self.live_data = data
            self.is_live = True
        except Exception:
            super().__init__()
            self.is_live = False
            self.live_data = {}

