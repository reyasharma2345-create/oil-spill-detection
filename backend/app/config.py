import os
from pydantic import BaseModel

class AppSettings(BaseModel):
    PROJECT_NAME: str = "PS26143 AI-Based Oil Spill Attribution System"
    VERSION: str = "1.0.0"
    API_PREFIX: str = "/api/v1"
    DEFAULT_CRS: str = "EPSG:4326"
    MAX_CANDIDATE_VESSELS: int = 10
    PARTICLE_COUNT_BACKTRACK: int = 500
    PARTICLE_COUNT_COUNTERFACTUAL: int = 400
    PARTICLE_COUNT_FORECAST: int = 600
    
    # Environmental default decay / drift parameters
    WIND_DRIFT_FACTOR: float = 0.03  # 3% windage rule
    CURRENT_DRIFT_FACTOR: float = 1.0  # 100% current transport
    DEFLECTION_ANGLE_DEG: float = 15.0  # Coriolis deflection angle in Northern hemisphere

settings = AppSettings()
