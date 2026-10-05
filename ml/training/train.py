"""
AEGIS-SPILL Model Training Pipeline
Implements complete PyTorch training loop with:
- Configurable optimizer (AdamW) & learning rate scheduler (ReduceLROnPlateau)
- Early stopping on validation loss / Dice score
- Best model checkpointing with complete metadata
- Full training history logging
- Automatic CPU fallback & GPU support
"""
import json
import random
import time
from pathlib import Path
from typing import Dict, Any, Optional
import numpy as np
import torch
import torch.optim as optim
from torch.optim.lr_scheduler import ReduceLROnPlateau
from torch.utils.data import DataLoader

from ml.config import MLConfig, config as default_config
from ml.models.model import SARUNet
from ml.training.losses import CombinedBCEDiceLoss
from ml.utils.metrics import calculate_segmentation_metrics


def set_seed(seed: int = 42):
    """Ensures complete reproducibility across Python, NumPy, and PyTorch."""
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed(seed)
        torch.cuda.manual_seed_all(seed)
        torch.backends.cudnn.deterministic = True
        torch.backends.cudnn.benchmark = False


def train_one_epoch(
    model: torch.nn.Module,
    loader: DataLoader,
    optimizer: torch.optim.Optimizer,
    criterion: torch.nn.Module,
    device: str,
) -> float:
    """Runs a single training epoch and returns the average batch loss."""
    model.train()
    running_loss = 0.0
    total_batches = len(loader)

    if total_batches == 0:
        return 0.0

    for images, masks, _ in loader:
        images = images.to(device)
        masks = masks.to(device)

        optimizer.zero_grad()
        logits = model(images)
        loss = criterion(logits, masks)
        loss.backward()
        optimizer.step()

        running_loss += loss.item()

    return running_loss / total_batches


def validate_one_epoch(
    model: torch.nn.Module,
    loader: DataLoader,
    criterion: torch.nn.Module,
    device: str,
    threshold: float = 0.5,
) -> Dict[str, float]:
    """Runs validation, computing loss and detailed segmentation metrics."""
    model.eval()
    running_loss = 0.0
    total_batches = len(loader)

    all_preds = []
    all_targets = []

    if total_batches == 0:
        return {"val_loss": 0.0, "iou": 0.0, "dice": 0.0, "precision": 0.0, "recall": 0.0}

    with torch.no_grad():
        for images, masks, _ in loader:
            images = images.to(device)
            masks = masks.to(device)

            logits = model(images)
            loss = criterion(logits, masks)
            running_loss += loss.item()

            probs = torch.sigmoid(logits).cpu().numpy()
            targets = masks.cpu().numpy()

            all_preds.append(probs)
            all_targets.append(targets)

    avg_loss = running_loss / total_batches

    all_preds = np.concatenate(all_preds, axis=0)
    all_targets = np.concatenate(all_targets, axis=0)

    metrics = calculate_segmentation_metrics(all_preds, all_targets, threshold=threshold)
    metrics["val_loss"] = round(avg_loss, 5)

    return metrics


def train_model(
    train_loader: DataLoader,
    val_loader: DataLoader,
    cfg: Optional[MLConfig] = None,
) -> Dict[str, Any]:
    """
    Executes complete training loop, saving the best model and returning training history.
    """
    if cfg is None:
        cfg = default_config
    cfg.ensure_directories()

    set_seed(cfg.SEED)
    device = cfg.DEVICE
    print(f"[AEGIS-SPILL ML] Starting training on device: {device}")

    # Model architecture
    model = SARUNet(
        in_channels=cfg.IN_CHANNELS,
        out_channels=cfg.NUM_CLASSES,
        features=[32, 64, 128],
        dropout=0.1,
    ).to(device)

    # Loss & Optimizer
    criterion = CombinedBCEDiceLoss(
        bce_weight=cfg.BCE_WEIGHT,
        dice_weight=cfg.DICE_WEIGHT,
        smooth=cfg.SMOOTH_FACTOR,
    )
    optimizer = optim.AdamW(
        model.parameters(),
        lr=cfg.LEARNING_RATE,
        weight_decay=cfg.WEIGHT_DECAY,
    )
    scheduler = ReduceLROnPlateau(
        optimizer,
        mode="min",
        factor=cfg.LR_SCHEDULER_FACTOR,
        patience=cfg.LR_SCHEDULER_PATIENCE,
        min_lr=cfg.MIN_LR,
    )

    history = {
        "train_loss": [],
        "val_loss": [],
        "val_iou": [],
        "val_dice": [],
        "val_precision": [],
        "val_recall": [],
        "learning_rates": [],
    }

    best_val_loss = float("inf")
    best_metrics = {}
    patience_counter = 0

    start_time = time.time()

    for epoch in range(1, cfg.NUM_EPOCHS + 1):
        epoch_start = time.time()
        
        train_loss = train_one_epoch(model, train_loader, optimizer, criterion, device)
        val_metrics = validate_one_epoch(model, val_loader, criterion, device, threshold=cfg.DETECTION_THRESHOLD)
        val_loss = val_metrics["val_loss"]

        current_lr = optimizer.param_groups[0]["lr"]
        scheduler.step(val_loss)

        # Record metrics
        history["train_loss"].append(round(train_loss, 5))
        history["val_loss"].append(val_loss)
        history["val_iou"].append(val_metrics["iou"])
        history["val_dice"].append(val_metrics["dice"])
        history["val_precision"].append(val_metrics["precision"])
        history["val_recall"].append(val_metrics["recall"])
        history["learning_rates"].append(current_lr)

        elapsed = time.time() - epoch_start
        print(
            f"Epoch [{epoch:02d}/{cfg.NUM_EPOCHS:02d}] ({elapsed:.1f}s) - "
            f"Train Loss: {train_loss:.4f} | Val Loss: {val_loss:.4f} | "
            f"Val IoU: {val_metrics['iou']:.4f} | Val Dice: {val_metrics['dice']:.4f} | LR: {current_lr:.2e}"
        )

        # Best Model Checkpointing
        if val_loss < best_val_loss:
            best_val_loss = val_loss
            best_metrics = val_metrics
            patience_counter = 0

            checkpoint = {
                "epoch": epoch,
                "model_state_dict": model.state_dict(),
                "optimizer_state_dict": optimizer.state_dict(),
                "val_loss": val_loss,
                "metrics": val_metrics,
                "config": {
                    "image_size": cfg.IMAGE_SIZE,
                    "in_channels": cfg.IN_CHANNELS,
                    "num_classes": cfg.NUM_CLASSES,
                    "detection_threshold": cfg.DETECTION_THRESHOLD,
                    "features": [32, 64, 128],
                    "model_version": "v1.0.0-sar-unet",
                }
            }
            torch.save(checkpoint, cfg.BEST_MODEL_PATH)
            print(f"  --> Checkpoint saved to: {cfg.BEST_MODEL_PATH}")
        else:
            patience_counter += 1
            if patience_counter >= cfg.EARLY_STOPPING_PATIENCE:
                print(f"[AEGIS-SPILL ML] Early stopping triggered at epoch {epoch}.")
                break

    total_training_time = time.time() - start_time
    print(f"[AEGIS-SPILL ML] Training complete in {total_training_time:.1f} seconds. Best Val Loss: {best_val_loss:.4f}")

    # Save training metrics log
    metrics_summary = {
        "best_epoch": checkpoint.get("epoch", epoch) if "checkpoint" in locals() else epoch,
        "best_metrics": best_metrics,
        "history": history,
        "total_training_time_sec": round(total_training_time, 2),
        "device": device,
    }
    with open(cfg.METRICS_LOG_PATH, "w") as f:
        json.dump(metrics_summary, f, indent=2)

    # Save model config
    with open(cfg.MODEL_CONFIG_PATH, "w") as f:
        json.dump(checkpoint.get("config", {}) if "checkpoint" in locals() else {}, f, indent=2)

    return metrics_summary
