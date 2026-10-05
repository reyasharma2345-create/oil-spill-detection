"""
AEGIS-SPILL Training Module
"""
from ml.training.losses import CombinedBCEDiceLoss, SoftDiceLoss
from ml.training.train import train_model

__all__ = ["CombinedBCEDiceLoss", "SoftDiceLoss", "train_model"]
