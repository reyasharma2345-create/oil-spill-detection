"""
AEGIS-SPILL ML Configuration Module
Defines hyperparameters, directory paths, and device settings.
"""
from dataclasses import dataclass, field
from pathlib import Path
from typing import Tuple, List
import torch


@dataclass
class MLConfig:
    # Project Paths (relative to project root)
    PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent
    DATA_DIR: Path = PROJECT_ROOT / "ml" / "datasets"
    MODELS_DIR: Path = PROJECT_ROOT / "models"
    OUTPUTS_DIR: Path = PROJECT_ROOT / "outputs"
    
    # Model Artifacts
    BEST_MODEL_PATH: Path = MODELS_DIR / "best_model.pth"
    MODEL_CONFIG_PATH: Path = MODELS_DIR / "model_config.json"
    METRICS_LOG_PATH: Path = OUTPUTS_DIR / "training_metrics.json"
    
    # Hardware Configuration
    DEVICE: str = "cuda" if torch.cuda.is_available() else "cpu"
    NUM_WORKERS: int = 0  # Safe default on Windows
    
    # Dataset & Preprocessing
    IMAGE_SIZE: Tuple[int, int] = (128, 128)
    IN_CHANNELS: int = 1  # 1 for SAR single-polarization (VV/VH), 3 for RGB/Optical
    NUM_CLASSES: int = 1   # Binary segmentation: 1 = Oil Spill, 0 = Background
    NORMALIZE_MEAN: float = 0.5
    NORMALIZE_STD: float = 0.5
    
    # Training Hyperparameters
    BATCH_SIZE: int = 4
    LEARNING_RATE: float = 1e-3
    WEIGHT_DECAY: float = 1e-4
    NUM_EPOCHS: int = 10
    EARLY_STOPPING_PATIENCE: int = 5
    LR_SCHEDULER_PATIENCE: int = 2
    LR_SCHEDULER_FACTOR: float = 0.5
    MIN_LR: float = 1e-6
    
    # Loss Function Balance
    BCE_WEIGHT: float = 0.5
    DICE_WEIGHT: float = 0.5
    SMOOTH_FACTOR: float = 1.0  # Laplace smoothing for Dice
    
    # Segmentation Decision Threshold
    DETECTION_THRESHOLD: float = 0.25
    MIN_SPILL_PIXELS: int = 10  # Minimum contiguous pixels to declare an oil spill event
    
    # Reproducibility
    SEED: int = 42

    def ensure_directories(self):
        """Ensure necessary runtime directories exist."""
        self.DATA_DIR.mkdir(parents=True, exist_ok=True)
        self.MODELS_DIR.mkdir(parents=True, exist_ok=True)
        self.OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
        (self.OUTPUTS_DIR / "visualizations").mkdir(parents=True, exist_ok=True)
        (self.OUTPUTS_DIR / "predictions").mkdir(parents=True, exist_ok=True)


config = MLConfig()
