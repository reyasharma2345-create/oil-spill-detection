"""
AEGIS-SPILL Smoke Dataset Generator
Generates a small, reproducible synthetic SAR oil spill dataset for pipeline verification,
smoke testing, and unit tests when full external benchmark datasets are pending download.
Also incorporates any existing local .npy test arrays.
"""
from pathlib import Path
import numpy as np
from PIL import Image

from ml.config import config


def generate_synthetic_sar_tile(
    size: int = 128,
    has_spill: bool = True,
    seed: int = 42
) -> tuple[np.ndarray, np.ndarray]:
    """
    Generates a realistic SAR sea surface tile with speckle noise and optional low-backscatter oil slick.
    SAR physics characteristics:
    - Sea background: Rayleigh/Gamma speckle distribution (moderate to high backscatter)
    - Oil slick: Dark patch dampening capillary waves (low radar backscatter)
    """
    rng = np.random.RandomState(seed)

    # 1. Base sea clutter with speckle noise
    sea_bg = rng.gamma(shape=4.0, scale=0.15, size=(size, size)).astype(np.float32)
    sea_bg = np.clip(sea_bg / sea_bg.max(), 0.15, 0.95)

    mask = np.zeros((size, size), dtype=np.uint8)

    if has_spill:
        # Generate an irregular slick (ellipse with Gaussian blur boundary)
        y, x = np.ogrid[:size, :size]
        cx = rng.randint(size // 4, 3 * size // 4)
        cy = rng.randint(size // 4, 3 * size // 4)
        rx = rng.randint(size // 8, size // 4)
        ry = rng.randint(size // 10, size // 5)
        angle = rng.uniform(0, np.pi)

        # Rotated ellipse coordinates
        cos_a, sin_a = np.cos(angle), np.sin(angle)
        dx = x - cx
        dy = y - cy
        x_rot = cos_a * dx + sin_a * dy
        y_rot = -sin_a * dx + cos_a * dy

        ellipse_eq = (x_rot / rx) ** 2 + (y_rot / ry) ** 2
        spill_region = ellipse_eq <= 1.0
        mask[spill_region] = 1

        # Oil dampens SAR backscatter by 40-70%
        sea_bg[spill_region] *= rng.uniform(0.2, 0.35)

    return sea_bg, mask


def create_smoke_dataset(output_dir: Path = None, num_samples: int = 12):
    """Creates a small multi-scene smoke dataset for pipeline validation."""
    if output_dir is None:
        output_dir = config.DATA_DIR / "smoke_dataset"
    
    images_dir = output_dir / "images"
    masks_dir = output_dir / "masks"
    images_dir.mkdir(parents=True, exist_ok=True)
    masks_dir.mkdir(parents=True, exist_ok=True)

    print(f"[AEGIS-SPILL ML] Generating smoke dataset at: {output_dir}")

    # Generate samples grouped into 3 distinct scenes
    for i in range(num_samples):
        scene_idx = (i // 4) + 1
        tile_idx = (i % 4) + 1
        has_spill = (i % 3 != 0)  # 2/3 with oil spill, 1/3 look-alike / clean water

        image, mask = generate_synthetic_sar_tile(size=128, has_spill=has_spill, seed=100 + i)
        base_name = f"scene_{scene_idx:02d}_tile_{tile_idx:02d}"

        # Save as both .png and .npy to verify dual format support
        if i % 2 == 0:
            np.save(images_dir / f"{base_name}.npy", image)
            np.save(masks_dir / f"{base_name}_mask.npy", mask)
        else:
            img_png = Image.fromarray((image * 255).astype(np.uint8))
            mask_png = Image.fromarray((mask * 255).astype(np.uint8))
            img_png.save(images_dir / f"{base_name}.png")
            mask_png.save(masks_dir / f"{base_name}_mask.png")

    # Also link/copy existing backend/test_sar.npy if present
    root_test_sar = config.PROJECT_ROOT / "backend" / "test_sar.npy"
    root_test_mask = config.PROJECT_ROOT / "backend" / "test_sar_mask.npy"
    if root_test_sar.exists() and root_test_mask.exists():
        sar_arr = np.load(root_test_sar)
        mask_arr = np.load(root_test_mask)
        np.save(images_dir / "scene_00_tile_01.npy", sar_arr)
        np.save(masks_dir / "scene_00_tile_01_mask.npy", mask_arr)

    print(f"[AEGIS-SPILL ML] Smoke dataset successfully created with {num_samples + 1} tiles.")
    return output_dir


if __name__ == "__main__":
    create_smoke_dataset()
