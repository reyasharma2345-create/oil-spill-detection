"""
AEGIS-SPILL Custom Loss Functions
Includes BCEWithLogitsLoss, Soft Dice Loss, and Combined Loss designed specifically
for extreme class imbalance in satellite imagery oil spill segmentation.
"""
import torch
import torch.nn as nn
import torch.nn.functional as F


class SoftDiceLoss(nn.Module):
    """
    Computes Soft Dice Loss on logits.
    Uses sigmoid to map logits to probabilities, then calculates intersection over union.
    """
    def __init__(self, smooth: float = 1.0):
        super().__init__()
        self.smooth = smooth

    def forward(self, logits: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
        probs = torch.sigmoid(logits)
        
        # Flatten spatial dimensions [B, C, H, W] => [B, -1]
        probs_flat = probs.view(probs.size(0), -1)
        targets_flat = targets.view(targets.size(0), -1)

        intersection = (probs_flat * targets_flat).sum(dim=1)
        total = probs_flat.sum(dim=1) + targets_flat.sum(dim=1)

        dice_score = (2.0 * intersection + self.smooth) / (total + self.smooth)
        return (1.0 - dice_score).mean()


class CombinedBCEDiceLoss(nn.Module):
    """
    Hybrid Objective Function:
    Loss = alpha * BCEWithLogitsLoss + (1 - alpha) * SoftDiceLoss
    
    Why this loss is optimal for satellite oil spills:
    - Satellite imagery is heavily imbalanced (sea background > 95%, slick < 5%).
    - BCE alone leads the network to predict all background pixels (collapsing to trivial local minima).
    - Dice Loss optimizes region overlap directly, heavily penalizing false negatives.
    - BCE provides smooth, non-vanishing gradient flow in early epochs.
    """
    def __init__(self, bce_weight: float = 0.5, dice_weight: float = 0.5, smooth: float = 1.0):
        super().__init__()
        self.bce_weight = bce_weight
        self.dice_weight = dice_weight
        self.bce = nn.BCEWithLogitsLoss()
        self.dice = SoftDiceLoss(smooth=smooth)

    def forward(self, logits: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
        loss_bce = self.bce(logits, targets)
        loss_dice = self.dice(logits, targets)
        return self.bce_weight * loss_bce + self.dice_weight * loss_dice
