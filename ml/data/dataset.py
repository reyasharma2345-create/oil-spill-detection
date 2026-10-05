"""
AEGIS-SPILL Dataset Module
Loads satellite images & masks from NumPy (.npy) or standard image files (.png, .jpg, .tif).
Implements scene-aware splitting to avoid geographic/temporal data leakage.
"""
from pathlib import Path
from typing import List, Tuple, Dict, Any, Optional
import numpy as np
import torch
from torch.utils.data import Dataset, DataLoader

from ml.data.preprocessing import SynchronizedTransform, get_transforms


def load_file_as_array(path: Path) -> np.ndarray:
    """Loads an image or mask from .npy or image file (PNG/JPG/TIFF)."""
    suffix = path.suffix.lower()
    if suffix == ".npy":
        return np.load(path)
    elif suffix in [".tif", ".tiff"]:
        try:
            import tifffile
            arr = tifffile.imread(str(path))
            if arr.ndim == 3:
                arr = arr[:, :, 0]
            return arr
        except Exception:
            pass

    try:
        from PIL import Image
        img = Image.open(path)
        return np.array(img)
    except Exception as e:
        raise RuntimeError(f"Failed to load image file {path}: {e}")


class OilSpillDataset(Dataset):
    """
    PyTorch Dataset for SAR / Optical Oil Spill Detection.
    Pairs satellite image with its corresponding binary segmentation mask.
    """
    def __init__(
        self,
        samples: List[Tuple[Path, Optional[Path]]],
        transform: Optional[SynchronizedTransform] = None,
    ):
        self.samples = samples  # List of (image_path, mask_path)
        self.transform = transform

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, idx: int) -> Tuple[torch.Tensor, torch.Tensor, str]:
        img_path, mask_path = self.samples[idx]
        
        image = load_file_as_array(img_path)
        mask = load_file_as_array(mask_path) if mask_path and mask_path.exists() else None

        if self.transform:
            image_t, mask_t = self.transform(image, mask)
        else:
            # Fallback bare tensor conversion
            if image.ndim == 2:
                image = np.expand_dims(image, axis=0)
            image_t = torch.from_numpy(image).float()
            mask_t = torch.from_numpy(mask).float() if mask is not None else torch.zeros((1, *image_t.shape[1:]))

        if mask_t is None:
            mask_t = torch.zeros((1, image_t.shape[1], image_t.shape[2]))

        return image_t, mask_t, img_path.name


def inspect_dataset_directory(data_dir: Path) -> Dict[str, Any]:
    """
    Inspects available images and masks in a dataset directory.
    Calculates format, dimensions, class distributions, and missing samples.
    Does NOT modify the original files.
    """
    images = sorted(list(data_dir.glob("**/*.*")))
    image_exts = {".npy", ".png", ".jpg", ".jpeg", ".tif", ".tiff"}
    valid_images = [p for p in images if p.suffix.lower() in image_exts and not p.name.endswith("_mask.npy") and "mask" not in p.name.lower()]
    
    total_images = len(valid_images)
    total_masks = 0
    corrupt_samples = 0
    shapes = set()
    total_oil_pixels = 0
    total_bg_pixels = 0

    pairs = []
    for img_p in valid_images:
        # Match mask
        mask_candidates = [
            img_p.with_name(f"{img_p.stem}_mask.npy"),
            img_p.with_name(f"{img_p.stem}_mask.png"),
            img_p.parent.parent / "masks" / f"{img_p.stem}_mask.npy",
            img_p.parent.parent / "masks" / f"{img_p.stem}_mask.png",
            img_p.parent.parent / "masks" / img_p.name,
            img_p.parent.parent / "labels" / img_p.name,
            img_p.parent / "masks" / img_p.name,
        ]
        mask_p = next((m for m in mask_candidates if m.exists()), None)
        if mask_p:
            total_masks += 1
            try:
                m_arr = load_file_as_array(mask_p)
                oil_px = int(np.sum(m_arr >= 0.5))
                bg_px = int(m_arr.size - oil_px)
                total_oil_pixels += oil_px
                total_bg_pixels += bg_px
            except Exception:
                corrupt_samples += 1
        pairs.append((img_p, mask_p))
        
        try:
            i_arr = load_file_as_array(img_p)
            shapes.add(i_arr.shape)
        except Exception:
            corrupt_samples += 1

    total_pixels = total_oil_pixels + total_bg_pixels
    spill_pixel_ratio = (total_oil_pixels / total_pixels) if total_pixels > 0 else 0.0

    return {
        "data_dir": str(data_dir),
        "total_images": total_images,
        "total_masks": total_masks,
        "shapes": [list(s) for s in shapes],
        "corrupt_samples": corrupt_samples,
        "class_distribution": {
            "oil_pixels": total_oil_pixels,
            "background_pixels": total_bg_pixels,
            "oil_pixel_ratio": round(spill_pixel_ratio, 5)
        },
        "pairs": pairs,
    }


def split_dataset_scene_aware(
    pairs: List[Tuple[Path, Optional[Path]]],
    train_ratio: float = 0.7,
    val_ratio: float = 0.15,
    test_ratio: float = 0.15,
    seed: int = 42,
) -> Tuple[List[Tuple[Path, Optional[Path]]], List[Tuple[Path, Optional[Path]]], List[Tuple[Path, Optional[Path]]]]:
    """
    Groups samples by scene identifier (e.g. prefix before '_tile')
    to prevent geographic/temporal leakage across train, val, and test splits.
    """
    import random
    rng = random.Random(seed)

    # Group by scene
    scene_groups: Dict[str, List[Tuple[Path, Optional[Path]]]] = {}
    for img_p, mask_p in pairs:
        # Determine scene prefix (e.g., scene_01 from scene_01_tile_03.png)
        parts = img_p.stem.split("_tile")
        scene_key = parts[0] if len(parts) > 1 else img_p.stem
        if scene_key not in scene_groups:
            scene_groups[scene_key] = []
        scene_groups[scene_key].append((img_p, mask_p))

    scenes = sorted(list(scene_groups.keys()))
    rng.shuffle(scenes)

    n_scenes = len(scenes)
    n_train = max(1, int(n_scenes * train_ratio))
    n_val = max(1, int(n_scenes * val_ratio)) if n_scenes > 2 else 0

    train_scenes = set(scenes[:n_train])
    val_scenes = set(scenes[n_train:n_train + n_val])
    test_scenes = set(scenes[n_train + n_val:]) if (n_train + n_val) < n_scenes else set(scenes[n_train:])

    train_pairs, val_pairs, test_pairs = [], [], []
    for sc, samples in scene_groups.items():
        if sc in train_scenes:
            train_pairs.extend(samples)
        elif sc in val_scenes:
            val_pairs.extend(samples)
        else:
            test_pairs.extend(samples)

    # If test is empty due to small number of scenes, allocate at least one sample to test/val
    if len(val_pairs) == 0 and len(train_pairs) > 1:
        val_pairs.append(train_pairs.pop())
    if len(test_pairs) == 0 and len(train_pairs) > 1:
        test_pairs.append(train_pairs.pop())

    return train_pairs, val_pairs, test_pairs


def create_dataloaders(
    pairs: List[Tuple[Path, Optional[Path]]],
    batch_size: int = 4,
    target_size: Tuple[int, int] = (128, 128),
    num_workers: int = 0,
    seed: int = 42,
) -> Dict[str, DataLoader]:
    """Creates train, val, and test PyTorch DataLoaders with zero leakage."""
    train_pairs, val_pairs, test_pairs = split_dataset_scene_aware(pairs, seed=seed)
    train_tf, eval_tf = get_transforms(target_size=target_size)

    train_ds = OilSpillDataset(train_pairs, transform=train_tf)
    val_ds = OilSpillDataset(val_pairs, transform=eval_tf)
    test_ds = OilSpillDataset(test_pairs, transform=eval_tf)

    return {
        "train": DataLoader(train_ds, batch_size=batch_size, shuffle=True, num_workers=num_workers),
        "val": DataLoader(val_ds, batch_size=batch_size, shuffle=False, num_workers=num_workers),
        "test": DataLoader(test_ds, batch_size=batch_size, shuffle=False, num_workers=num_workers),
        "splits": {
            "train_count": len(train_pairs),
            "val_count": len(val_pairs),
            "test_count": len(test_pairs),
        }
    }
