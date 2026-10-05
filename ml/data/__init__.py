"""
AEGIS-SPILL Data Module
Handles dataset loading, scene grouping, and synchronized transformations.
"""
from ml.data.dataset import OilSpillDataset, create_dataloaders
from ml.data.preprocessing import get_transforms

__all__ = ["OilSpillDataset", "create_dataloaders", "get_transforms"]
