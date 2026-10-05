"""
AEGIS-SPILL Evaluation & Visualization Pipeline
Calculates IoU, Dice/F1, Precision, Recall, Pixel Accuracy, Confusion Matrix.
Produces 4-panel visual verification outputs:
[Original Satellite Tile | Ground Truth Mask | Predicted Mask | High-Contrast Detection Overlay]
Plots training loss & metric curves.
"""
import json
from pathlib import Path
from typing import Dict, Any, Optional
import numpy as np
import torch
from torch.utils.data import DataLoader

from ml.config import MLConfig, config as default_config
from ml.models.model import SARUNet
from ml.utils.metrics import calculate_segmentation_metrics


def create_overlay_rgb(image: np.ndarray, mask: np.ndarray, color=(255, 0, 0), alpha=0.4) -> np.ndarray:
    """
    Creates an RGB overlay blending binary prediction mask over the original image.
    Color default is red for oil spill slicks.
    """
    if image.ndim == 2:
        # Grayscale to RGB
        base = np.stack([image, image, image], axis=-1)
    elif image.ndim == 3 and image.shape[0] in (1, 3):
        base = np.transpose(image, (1, 2, 0))
        if base.shape[-1] == 1:
            base = np.repeat(base, 3, axis=-1)
    else:
        base = image.copy()

    # Normalize base to 0-255 uint8
    if base.max() <= 1.0:
        base = (base * 255).astype(np.uint8)
    else:
        base = base.astype(np.uint8)

    overlay = base.copy()
    mask_bin = mask >= 0.5
    for c in range(3):
        overlay[:, :, c] = np.where(
            mask_bin,
            np.clip(base[:, :, c] * (1 - alpha) + color[c] * alpha, 0, 255).astype(np.uint8),
            base[:, :, c]
        )
    return overlay


def save_image_array(array: np.ndarray, output_path: Path):
    """Saves 2D/3D numpy array to disk as PNG."""
    try:
        from PIL import Image
        if array.dtype != np.uint8:
            if array.max() <= 1.0:
                array = (array * 255).astype(np.uint8)
            else:
                array = array.astype(np.uint8)
        img = Image.fromarray(array)
        img.save(output_path)
    except ImportError:
        # Fallback: save as .npy if PIL is unavailable
        np.save(output_path.with_suffix(".npy"), array)


def generate_visual_overlays(
    model: torch.nn.Module,
    loader: DataLoader,
    output_dir: Path,
    device: str,
    threshold: float = 0.5,
    max_samples: int = 5,
):
    """
    Generates 4-panel visual comparison tiles for qualitative inspection:
    1. Original Image
    2. Ground Truth Mask
    3. Predicted Mask
    4. Oil Spill Red Overlay
    """
    model.eval()
    output_dir.mkdir(parents=True, exist_ok=True)
    count = 0

    with torch.no_grad():
        for images, masks, filenames in loader:
            images = images.to(device)
            probs = model(images, return_prob=True).cpu().numpy()

            for i in range(len(filenames)):
                if count >= max_samples:
                    return

                fname = Path(filenames[i]).stem
                img_raw = images[i, 0].cpu().numpy()
                # De-normalize
                img_raw = img_raw * 0.5 + 0.5
                img_raw = np.clip(img_raw, 0.0, 1.0)

                gt_mask = masks[i, 0].cpu().numpy()
                pred_prob = probs[i, 0]
                pred_mask = (pred_prob >= threshold).astype(np.uint8)

                # Build overlay
                overlay = create_overlay_rgb(img_raw, pred_mask, color=(255, 30, 30), alpha=0.45)

                # Save individual visualizations
                save_image_array(img_raw, output_dir / f"{fname}_original.png")
                save_image_array(gt_mask * 255, output_dir / f"{fname}_ground_truth.png")
                save_image_array(pred_mask * 255, output_dir / f"{fname}_predicted.png")
                save_image_array(overlay, output_dir / f"{fname}_overlay.png")

                # Combine into side-by-side comparison strip
                try:
                    from PIL import Image
                    h, w = img_raw.shape
                    orig_img = Image.fromarray((img_raw * 255).astype(np.uint8)).convert("RGB")
                    gt_img = Image.fromarray((gt_mask * 255).astype(np.uint8)).convert("RGB")
                    pred_img = Image.fromarray((pred_mask * 255).astype(np.uint8)).convert("RGB")
                    over_img = Image.fromarray(overlay)

                    strip = Image.new("RGB", (w * 4, h))
                    strip.paste(orig_img, (0, 0))
                    strip.paste(gt_img, (w, 0))
                    strip.paste(pred_img, (w * 2, 0))
                    strip.paste(over_img, (w * 3, 0))
                    strip.save(output_dir / f"{fname}_panel_comparison.png")
                except Exception:
                    pass

                count += 1


def plot_training_curves(metrics_log_path: Path, output_dir: Path):
    """Plots training and validation loss/IoU curves if matplotlib is available."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        with open(metrics_log_path, "r") as f:
            data = json.load(f)

        hist = data.get("history", {})
        epochs = list(range(1, len(hist.get("train_loss", [])) + 1))
        if not epochs:
            return

        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))

        # Loss curve
        ax1.plot(epochs, hist.get("train_loss", []), "o-", label="Train Loss", color="#1E88E5")
        ax1.plot(epochs, hist.get("val_loss", []), "s--", label="Val Loss", color="#E53935")
        ax1.set_title("Training & Validation Loss")
        ax1.set_xlabel("Epoch")
        ax1.set_ylabel("Loss")
        ax1.grid(True, linestyle="--", alpha=0.6)
        ax1.legend()

        # Metrics curve
        ax2.plot(epochs, hist.get("val_iou", []), "o-", label="Val IoU", color="#43A047")
        ax2.plot(epochs, hist.get("val_dice", []), "^-", label="Val Dice (F1)", color="#FB8C00")
        ax2.set_title("Validation Segmentation Performance")
        ax2.set_xlabel("Epoch")
        ax2.set_ylabel("Score")
        ax2.grid(True, linestyle="--", alpha=0.6)
        ax2.legend()

        plt.tight_layout()
        plt.savefig(output_dir / "training_curves.png", dpi=200)
        plt.close()
    except Exception as e:
        print(f"[AEGIS-SPILL ML] Matplotlib curve plotting skipped: {e}")


def evaluate_model(
    test_loader: DataLoader,
    checkpoint_path: Optional[Path] = None,
    cfg: Optional[MLConfig] = None,
) -> Dict[str, Any]:
    """
    Evaluates the saved model on the test dataset.
    Returns complete metrics dictionary and generates visual overlays.
    """
    if cfg is None:
        cfg = default_config
    if checkpoint_path is None:
        checkpoint_path = cfg.BEST_MODEL_PATH

    if not checkpoint_path.exists():
        raise FileNotFoundError(f"Model checkpoint not found at: {checkpoint_path}")

    device = cfg.DEVICE
    checkpoint = torch.load(checkpoint_path, map_location=device)

    model = SARUNet(
        in_channels=cfg.IN_CHANNELS,
        out_channels=cfg.NUM_CLASSES,
        features=checkpoint.get("config", {}).get("features", [32, 64, 128]),
    ).to(device)
    model.load_state_dict(checkpoint["model_state_dict"])
    model.eval()

    all_preds = []
    all_targets = []

    with torch.no_grad():
        for images, masks, _ in test_loader:
            images = images.to(device)
            probs = model(images, return_prob=True).cpu().numpy()
            targets = masks.cpu().numpy()
            all_preds.append(probs)
            all_targets.append(targets)

    if len(all_preds) > 0:
        all_preds = np.concatenate(all_preds, axis=0)
        all_targets = np.concatenate(all_targets, axis=0)
        metrics = calculate_segmentation_metrics(all_preds, all_targets, threshold=cfg.DETECTION_THRESHOLD)
    else:
        metrics = {"iou": 0.0, "dice": 0.0, "precision": 0.0, "recall": 0.0, "pixel_accuracy": 0.0}

    # Generate visual outputs
    vis_dir = cfg.OUTPUTS_DIR / "visualizations"
    generate_visual_overlays(model, test_loader, vis_dir, device, threshold=cfg.DETECTION_THRESHOLD)

    # Plot loss curves if metrics exist
    if cfg.METRICS_LOG_PATH.exists():
        plot_training_curves(cfg.METRICS_LOG_PATH, vis_dir)

    # Save test results
    test_results_path = cfg.OUTPUTS_DIR / "test_evaluation_metrics.json"
    with open(test_results_path, "w") as f:
        json.dump(metrics, f, indent=2)

    return metrics
