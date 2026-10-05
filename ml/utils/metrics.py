"""
AEGIS-SPILL Evaluation Metrics Module
Computes IoU, Dice/F1, Precision, Recall, Pixel Accuracy, and Confusion Matrix for binary segmentation.
"""
from typing import Dict, Any
import numpy as np
import torch


def compute_confusion_matrix(pred: np.ndarray, target: np.ndarray, threshold: float = 0.5) -> Dict[str, int]:
    """
    Computes True Positives, False Positives, True Negatives, and False Negatives.
    Inputs can be binary or float probability maps.
    """
    pred_bin = (pred >= threshold).astype(bool)
    target_bin = (target >= 0.5).astype(bool)

    tp = int(np.sum(pred_bin & target_bin))
    fp = int(np.sum(pred_bin & ~target_bin))
    tn = int(np.sum(~pred_bin & ~target_bin))
    fn = int(np.sum(~pred_bin & target_bin))

    return {
        "true_positives": tp,
        "false_positives": fp,
        "true_negatives": tn,
        "false_negatives": fn,
    }


def calculate_segmentation_metrics(
    pred: np.ndarray,
    target: np.ndarray,
    threshold: float = 0.5,
    eps: float = 1e-7
) -> Dict[str, float]:
    """
    Calculates comprehensive segmentation metrics:
    - IoU (Intersection over Union / Jaccard Index)
    - Dice / F1 Score
    - Precision
    - Recall (Sensitivity)
    - Specificity
    - Pixel Accuracy
    """
    cm = compute_confusion_matrix(pred, target, threshold=threshold)
    tp = cm["true_positives"]
    fp = cm["false_positives"]
    tn = cm["true_negatives"]
    fn = cm["false_negatives"]

    # IoU = TP / (TP + FP + FN)
    iou = (tp + eps) / (tp + fp + fn + eps) if (tp + fp + fn) > 0 else (1.0 if (tp + fp + fn) == 0 else 0.0)

    # Dice = 2*TP / (2*TP + FP + FN)
    dice = (2.0 * tp + eps) / (2.0 * tp + fp + fn + eps) if (2 * tp + fp + fn) > 0 else 1.0

    # Precision = TP / (TP + FP)
    precision = (tp + eps) / (tp + fp + eps) if (tp + fp) > 0 else 1.0

    # Recall = TP / (TP + FN)
    recall = (tp + eps) / (tp + fn + eps) if (tp + fn) > 0 else 1.0

    # Specificity = TN / (TN + FP)
    specificity = (tn + eps) / (tn + fp + eps) if (tn + fp) > 0 else 1.0

    # Accuracy = (TP + TN) / Total
    total = tp + fp + tn + fn
    accuracy = (tp + tn) / total if total > 0 else 1.0

    return {
        "iou": round(float(iou), 5),
        "dice": round(float(dice), 5),
        "f1_score": round(float(dice), 5),
        "precision": round(float(precision), 5),
        "recall": round(float(recall), 5),
        "specificity": round(float(specificity), 5),
        "pixel_accuracy": round(float(accuracy), 5),
        "confusion_matrix": cm,
    }
