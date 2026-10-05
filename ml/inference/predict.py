"""
AEGIS-SPILL High-Performance Inference Engine
Loads trained model checkpoint once, preprocesses arbitrary satellite tiles,
generates binary oil spill segmentation masks, computes spill area metrics,
and saves prediction masks & overlays.
"""
from pathlib import Path
from typing import Union, Dict, Any, Optional
import numpy as np
import torch

from ml.config import MLConfig, config as default_config
from ml.data.preprocessing import SynchronizedTransform
from ml.evaluation.evaluate import create_overlay_rgb, save_image_array
from ml.models.model import SARUNet


class SpillPredictor:
    """
    Inference wrapper for the AEGIS-SPILL SAR U-Net detector.
    Caches model in memory for fast repeated evaluations.
    """
    def __init__(
        self,
        checkpoint_path: Optional[Union[str, Path]] = None,
        cfg: Optional[MLConfig] = None,
        device: Optional[str] = None,
    ):
        self.cfg = cfg or default_config
        self.device = device or self.cfg.DEVICE
        self.checkpoint_path = Path(checkpoint_path) if checkpoint_path else self.cfg.BEST_MODEL_PATH
        
        self.transform = SynchronizedTransform(
            target_size=self.cfg.IMAGE_SIZE,
            is_training=False,
            normalize_mean=self.cfg.NORMALIZE_MEAN,
            normalize_std=self.cfg.NORMALIZE_STD,
        )

        self.model_version = "v1.0.0-sar-unet"
        self.model = self._load_model()

    def _load_model(self) -> torch.nn.Module:
        """Loads model weights from checkpoint if available, or initializes model architecture."""
        model = SARUNet(
            in_channels=self.cfg.IN_CHANNELS,
            out_channels=self.cfg.NUM_CLASSES,
            features=[32, 64, 128],
        ).to(self.device)

        if self.checkpoint_path.exists():
            print(f"[AEGIS-SPILL ML] Loading model weights from: {self.checkpoint_path}")
            checkpoint = torch.load(self.checkpoint_path, map_location=self.device)
            if "model_state_dict" in checkpoint:
                model.load_state_dict(checkpoint["model_state_dict"])
                self.model_version = checkpoint.get("config", {}).get("model_version", self.model_version)
            else:
                model.load_state_dict(checkpoint)
        else:
            print(f"[AEGIS-SPILL ML] Warning: Checkpoint {self.checkpoint_path} not found. Running initialized baseline.")

        model.eval()
        return model

    def predict(
        self,
        image_input: Union[str, Path, np.ndarray],
        threshold: Optional[float] = None,
        save_outputs: bool = True,
        output_prefix: str = "spill_prediction",
    ) -> Dict[str, Any]:
        """
        Executes inference on input satellite image.
        
        Parameters:
            image_input: Path to image (.npy, .png, .jpg, .tif) or NumPy array.
            threshold: Confidence threshold for slick pixel classification.
            save_outputs: Whether to save predicted mask and visual overlay.
            output_prefix: File prefix for saved outputs.
            
        Returns:
            Structured JSON dictionary compatible with AEGIS-SPILL backend.
        """
        det_threshold = threshold if threshold is not None else self.cfg.DETECTION_THRESHOLD

        # 1. Load image to numpy array
        if isinstance(image_input, (str, Path)):
            path = Path(image_input)
            if not path.exists():
                raise FileNotFoundError(f"Input image not found: {path}")
            if path.suffix.lower() == ".npy":
                img_array = np.load(path)
            elif path.suffix.lower() in [".tif", ".tiff"]:
                try:
                    import tifffile
                    img_array = tifffile.imread(str(path))
                    if img_array.ndim == 3:
                        img_array = img_array[:, :, 0]
                    # Normalize backscatter if float
                    if img_array.dtype in [np.float32, np.float64] and img_array.min() < 0:
                        vmin, vmax = -45.0, -10.0
                        img_array = np.clip((img_array - vmin) / (vmax - vmin), 0.0, 1.0)
                except Exception:
                    from PIL import Image
                    img_array = np.array(Image.open(path).convert("L"))
            else:
                from PIL import Image
                img = Image.open(path)
                # SAR amplitude is single-channel; convert RGB quicklooks to single-channel (L)
                img_array = np.array(img.convert("L"))
            if output_prefix == "spill_prediction":
                output_prefix = path.stem
        elif isinstance(image_input, np.ndarray):
            img_array = image_input
            if img_array.ndim == 3:
                if img_array.shape[-1] == 3 or img_array.shape[-1] == 4:
                    img_array = np.mean(img_array[:, :, :3], axis=-1)
                elif img_array.shape[-1] == 1:
                    img_array = img_array[:, :, 0]
                elif img_array.shape[0] in [1, 3, 4]:
                    img_array = np.mean(img_array[:3, :, :], axis=0)
        else:
            raise ValueError(f"Unsupported image input type: {type(image_input)}")

        orig_shape = img_array.shape[:2]

        # 2. Preprocess
        tensor_in, _ = self.transform(img_array)
        tensor_in = tensor_in.unsqueeze(0).to(self.device)  # [1, C, H, W]

        # 3. Model forward pass
        with torch.no_grad():
            prob_tensor = self.model(tensor_in, return_prob=True)
            prob_map = prob_tensor.squeeze().cpu().numpy()

        # 4. Generate binary segmentation mask
        binary_mask = (prob_map >= det_threshold).astype(np.uint8)

        # 5. Compute detection metrics
        spill_pixels = int(np.sum(binary_mask))
        total_pixels = binary_mask.size
        spill_ratio = round(float(spill_pixels / total_pixels), 6)
        
        # Mean confidence over identified slick region (or max probability across the tile)
        if spill_pixels > 0:
            confidence = float(np.mean(prob_map[binary_mask == 1]))
        else:
            confidence = float(np.max(prob_map)) if prob_map.size > 0 else 0.0

        is_oil_detected = bool(spill_pixels >= self.cfg.MIN_SPILL_PIXELS)

        mask_path_str = None
        overlay_path_str = None

        # 6. Save outputs if requested
        if save_outputs:
            preds_dir = self.cfg.OUTPUTS_DIR / "predictions"
            preds_dir.mkdir(parents=True, exist_ok=True)

            mask_file = preds_dir / f"{output_prefix}_mask.png"
            overlay_file = preds_dir / f"{output_prefix}_overlay.png"
            npy_mask_file = preds_dir / f"{output_prefix}_mask.npy"

            # Save numpy mask
            np.save(npy_mask_file, binary_mask)

            # Save visual mask (0-255 PNG)
            save_image_array(binary_mask * 255, mask_file)

            # Generate and save overlay
            denorm_img = (tensor_in.squeeze().cpu().numpy() * self.cfg.NORMALIZE_STD) + self.cfg.NORMALIZE_MEAN
            denorm_img = np.clip(denorm_img, 0.0, 1.0)
            overlay = create_overlay_rgb(denorm_img, binary_mask, color=(255, 30, 30), alpha=0.45)
            save_image_array(overlay, overlay_file)

            mask_path_str = str(mask_file)
            overlay_path_str = str(overlay_file)

        return {
            "oil_spill_detected": is_oil_detected,
            "confidence": round(confidence, 4),
            "spill_area_pixels": spill_pixels,
            "total_pixels": total_pixels,
            "spill_ratio": spill_ratio,
            "threshold": det_threshold,
            "mask_path": mask_path_str,
            "overlay_path": overlay_path_str,
            "model_version": self.model_version,
            "input_resolution": list(orig_shape),
            "processed_resolution": list(self.cfg.IMAGE_SIZE),
        }


# Singleton instance for efficient FastAPI reuse
_GLOBAL_PREDICTOR: Optional[SpillPredictor] = None

def get_default_predictor() -> SpillPredictor:
    """Returns the shared cached SpillPredictor instance."""
    global _GLOBAL_PREDICTOR
    if _GLOBAL_PREDICTOR is None:
        _GLOBAL_PREDICTOR = SpillPredictor()
    return _GLOBAL_PREDICTOR
