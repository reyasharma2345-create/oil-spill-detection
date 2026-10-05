"""
AEGIS-SPILL Image & Mask Preprocessing Pipeline
Provides synchronized data augmentations for training and deterministic transforms for validation/inference.
"""
import random
from typing import Tuple, Optional
import numpy as np
import torch
import torch.nn.functional as F


class SynchronizedTransform:
    """
    Applies synchronized spatial transformations to paired satellite image and segmentation mask.
    Ensures zero augmentation leakage for validation and testing.
    """
    def __init__(
        self,
        target_size: Tuple[int, int] = (128, 128),
        is_training: bool = False,
        normalize_mean: float = 0.5,
        normalize_std: float = 0.5,
        horizontal_flip_prob: float = 0.5,
        vertical_flip_prob: float = 0.5,
        rotate90_prob: float = 0.5,
    ):
        self.target_size = target_size
        self.is_training = is_training
        self.normalize_mean = normalize_mean
        self.normalize_std = normalize_std
        self.hflip_p = horizontal_flip_prob
        self.vflip_p = vertical_flip_prob
        self.rot90_p = rotate90_prob

    def _resize_array(self, arr: np.ndarray, target_shape: Tuple[int, int], is_mask: bool) -> np.ndarray:
        """Resizes 2D/3D numpy array using bilinear (image) or nearest (mask) interpolation."""
        h, w = arr.shape[:2]
        if (h, w) == target_shape:
            return arr

        # Shape to tensor [1, C, H, W]
        if arr.ndim == 2:
            t = torch.from_numpy(arr).unsqueeze(0).unsqueeze(0).float()
        elif arr.ndim == 3:
            t = torch.from_numpy(arr).permute(2, 0, 1).unsqueeze(0).float()
        else:
            raise ValueError(f"Unsupported array dimensions: {arr.ndim}")

        mode = "nearest" if is_mask else "bilinear"
        align_corners = None if is_mask else False

        resized = F.interpolate(t, size=target_shape, mode=mode, align_corners=align_corners)

        if arr.ndim == 2:
            return resized.squeeze().numpy()
        else:
            return resized.squeeze(0).permute(1, 2, 0).numpy()

    def __call__(
        self,
        image: np.ndarray,
        mask: Optional[np.ndarray] = None
    ) -> Tuple[torch.Tensor, Optional[torch.Tensor]]:
        """
        Processes image and optional mask.
        Image is expected as (H, W) or (H, W, C).
        Mask is expected as (H, W) with binary values 0 or 1.
        """
        # 1. Resize to target dimensions
        image = self._resize_array(image, self.target_size, is_mask=False)
        if mask is not None:
            mask = self._resize_array(mask, self.target_size, is_mask=True)

        # 2. Synchronized Data Augmentation (Training only)
        if self.is_training:
            # Horizontal flip
            if random.random() < self.hflip_p:
                image = np.fliplr(image)
                if mask is not None:
                    mask = np.fliplr(mask)

            # Vertical flip
            if random.random() < self.vflip_p:
                image = np.flipud(image)
                if mask is not None:
                    mask = np.flipud(mask)

            # Random 90-degree rotations
            if random.random() < self.rot90_p:
                k = random.choice([1, 2, 3])
                image = np.rot90(image, k)
                if mask is not None:
                    mask = np.rot90(mask, k)

        # 3. Channel formatting: ensure (C, H, W)
        if image.ndim == 2:
            image = np.expand_dims(image, axis=0)  # (1, H, W)
        elif image.ndim == 3:
            image = np.transpose(image, (2, 0, 1))  # (C, H, W)

        # 4. Normalization
        image = image.astype(np.float32)
        # If image values are in [0, 255], scale to [0, 1]
        if image.max() > 1.0:
            image = image / 255.0

        # Standardize
        image = (image - self.normalize_mean) / (self.normalize_std + 1e-7)

        image_tensor = torch.from_numpy(image.copy()).float()

        # 5. Mask formatting: (1, H, W) binary float32 tensor
        mask_tensor = None
        if mask is not None:
            mask = mask.astype(np.float32)
            # Threshold to clean binary 0 or 1
            mask = (mask >= 0.5).astype(np.float32)
            if mask.ndim == 2:
                mask = np.expand_dims(mask, axis=0)
            elif mask.ndim == 3 and mask.shape[2] == 1:
                mask = np.transpose(mask, (2, 0, 1))
            mask_tensor = torch.from_numpy(mask.copy()).float()

        return image_tensor, mask_tensor


def get_transforms(
    target_size: Tuple[int, int] = (128, 128),
    normalize_mean: float = 0.5,
    normalize_std: float = 0.5,
) -> Tuple[SynchronizedTransform, SynchronizedTransform]:
    """Returns (train_transform, eval_transform)."""
    train_tf = SynchronizedTransform(
        target_size=target_size,
        is_training=True,
        normalize_mean=normalize_mean,
        normalize_std=normalize_std,
    )
    eval_tf = SynchronizedTransform(
        target_size=target_size,
        is_training=False,
        normalize_mean=normalize_mean,
        normalize_std=normalize_std,
    )
    return train_tf, eval_tf
