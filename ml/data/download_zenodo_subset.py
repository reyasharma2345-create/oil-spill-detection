"""
AEGIS-SPILL Real Zenodo Sentinel-1 SAR Dataset Ingestion Pipeline
Downloads real Sentinel-1 SAR scenes and official ground truth masks from Zenodo/HF mirror,
crops them into standardized spatial patches, preserves oil vs background balance,
and prepares them for SAR U-Net training and evaluation.
"""
import os
import sys
import argparse
import subprocess
from pathlib import Path
import numpy as np
from PIL import Image

try:
    import tifffile
except ImportError:
    tifffile = None

try:
    import py7zr
except ImportError:
    py7zr = None


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_OUT_DIR = PROJECT_ROOT / "ml" / "datasets" / "zenodo_sentinel1"
HF_BASE_URL = "https://huggingface.co/datasets/yuvaakash1610/01_Train_Val_Oil_Spill_images/resolve/main"
ZENODO_MASK_URL = "https://zenodo.org/records/8346860/files/01_Train_Val_Oil_Spill_mask.7z?download=1"


def download_file(url: str, dest_path: Path) -> bool:
    """Downloads a file using curl.exe if available or urllib."""
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    if dest_path.exists() and dest_path.stat().st_size > 1000:
        print(f"  [Cache] {dest_path.name} already exists.")
        return True

    print(f"  [Download] Fetching {url} -> {dest_path.name}...")
    # Try curl.exe first (fastest and supports redirects seamlessly)
    try:
        ret = subprocess.run(
            ["curl.exe", "-sL", url, "-o", str(dest_path)],
            check=True,
            timeout=300
        )
        if dest_path.exists() and dest_path.stat().st_size > 1000:
            return True
    except Exception as e:
        print(f"  [Warning] curl failed ({e}), trying urllib...")

    import urllib.request
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req) as resp, open(dest_path, "wb") as f:
        f.write(resp.read())
    return dest_path.exists() and dest_path.stat().st_size > 1000


def ensure_masks_extracted(datasets_dir: Path) -> Path:
    """Ensures official Zenodo Part I masks archive is downloaded and extracted."""
    mask_dir = datasets_dir / "zenodo_masks_raw" / "Mask_oil"
    if mask_dir.exists() and len(list(mask_dir.glob("*.tif"))) > 100:
        print(f"  [Ready] Zenodo ground truth masks found in {mask_dir}")
        return mask_dir

    mask_archive = datasets_dir / "01_Train_Val_Oil_Spill_mask.7z"
    download_file(ZENODO_MASK_URL, mask_archive)

    print(f"  [Extract] Extracting {mask_archive.name}...")
    import py7zr
    archive = py7zr.SevenZipFile(mask_archive, 'r')
    archive.extractall(path=datasets_dir / "zenodo_masks_raw")
    return mask_dir


def crop_scene_into_tiles(
    image_path: Path,
    mask_path: Path,
    images_out_dir: Path,
    masks_out_dir: Path,
    tile_size: int = 128,
    min_oil_pixels: int = 20,
    keep_bg_ratio: float = 0.5,
) -> int:
    """
    Crops a full 2048x2048 SAR scene and mask into tile_size x tile_size patches.
    Saves positive (oil spill) and representative negative (clean sea) patches.
    """
    import tifffile
    sar_img = tifffile.imread(str(image_path))
    mask_img = np.array(Image.open(str(mask_path)))

    # Take VV polarization (band 0) if multi-channel
    if sar_img.ndim == 3:
        sar_band = sar_img[:, :, 0]
    else:
        sar_band = sar_img

    # SAR backscatter normalization: typically in range [-50, -5] dB
    # Clip extreme outliers and scale linearly to [0, 1]
    vmin, vmax = -45.0, -10.0
    norm_band = np.clip((sar_band - vmin) / (vmax - vmin), 0.0, 1.0).astype(np.float32)

    h, w = norm_band.shape
    scene_id = image_path.stem

    pos_count = 0
    neg_count = 0
    saved_count = 0

    step = tile_size  # Non-overlapping grid
    for y in range(0, h - tile_size + 1, step):
        for x in range(0, w - tile_size + 1, step):
            tile_img = norm_band[y:y+tile_size, x:x+tile_size]
            tile_mask = (mask_img[y:y+tile_size, x:x+tile_size] > 0).astype(np.uint8)

            oil_px = int(np.sum(tile_mask))
            is_oil = oil_px >= min_oil_pixels

            # Decision to keep
            if is_oil:
                pos_count += 1
                keep = True
            else:
                # Keep background sea clutter with probability to avoid massive class imbalance
                if np.random.rand() < keep_bg_ratio:
                    neg_count += 1
                    keep = True
                else:
                    keep = False

            if keep:
                tile_name = f"scene_{scene_id}_y{y}_x{x}"
                # Save as numpy array (.npy) and preview PNG (.png)
                img_npy_path = images_out_dir / f"{tile_name}.npy"
                mask_npy_path = masks_out_dir / f"{tile_name}_mask.npy"

                np.save(img_npy_path, tile_img)
                np.save(mask_npy_path, tile_mask)

                # Save 8-bit PNG for visual inspections and web demos
                img_8bit = (tile_img * 255.0).astype(np.uint8)
                mask_8bit = (tile_mask * 255).astype(np.uint8)
                Image.fromarray(img_8bit).save(images_out_dir / f"{tile_name}.png")
                Image.fromarray(mask_8bit).save(masks_out_dir / f"{tile_name}_mask.png")

                saved_count += 1

    print(f"    Scene {scene_id}: Saved {saved_count} tiles ({pos_count} oil, {neg_count} sea background)")
    return saved_count


def prepare_zenodo_dataset(
    target_scenes: list = None,
    tile_size: int = 128,
    out_dir: Path = DEFAULT_OUT_DIR
):
    """Downloads real scenes and builds the Zenodo Sentinel-1 dataset."""
    if target_scenes is None:
        # Default high-quality scenes with clear oil slicks
        target_scenes = ["00642", "00643", "00644", "00646"]

    datasets_dir = PROJECT_ROOT / "ml" / "datasets"
    masks_dir = ensure_masks_extracted(datasets_dir)

    images_out = out_dir / "images"
    masks_out = out_dir / "masks"
    images_out.mkdir(parents=True, exist_ok=True)
    masks_out.mkdir(parents=True, exist_ok=True)

    test_samples_dir = out_dir / "test_samples"
    test_samples_dir.mkdir(parents=True, exist_ok=True)

    total_tiles = 0
    for idx, scene_id in enumerate(target_scenes):
        print(f"\n[{idx+1}/{len(target_scenes)}] Processing Scene {scene_id}...")
        scene_file = datasets_dir / f"{scene_id}.tif"
        mask_file = masks_dir / f"{scene_id}.tif"

        if not mask_file.exists():
            print(f"  [Skip] Mask for scene {scene_id} not found.")
            continue

        # Download image from mirror
        url = f"{HF_BASE_URL}/{scene_id}.tif"
        success = download_file(url, scene_file)
        if not success:
            print(f"  [Error] Failed to download {scene_id}.tif")
            continue

        # Crop into training patches
        tiles = crop_scene_into_tiles(
            image_path=scene_file,
            mask_path=mask_file,
            images_out_dir=images_out,
            masks_out_dir=masks_out,
            tile_size=tile_size
        )
        total_tiles += tiles

        # Save an extracted real crop as a test sample for standalone inference
        if idx == 0:
            import tifffile
            full_img = tifffile.imread(str(scene_file))
            if full_img.ndim == 3:
                full_img = full_img[:, :, 0]
            # Crop a 512x512 region centered on the spill
            crop_512 = full_img[500:1012, 500:1012]
            sample_tif = test_samples_dir / "real_sentinel1_spill_scene.tif"
            tifffile.imwrite(str(sample_tif), crop_512)

            # Also save normalized 8-bit PNG for frontend demo
            vmin, vmax = -45.0, -10.0
            norm_512 = np.clip((crop_512 - vmin) / (vmax - vmin), 0.0, 1.0)
            png_512 = (norm_512 * 255.0).astype(np.uint8)
            frontend_public = PROJECT_ROOT / "frontend" / "public" / "sample_sar_tile.png"
            Image.fromarray(png_512).save(frontend_public)
            print(f"  [Demo Ready] Saved real Sentinel-1 crop to {frontend_public}")

    print(f"\n=======================================================")
    print(f"REAL ZENODO SENTINEL-1 DATASET GENERATION COMPLETE")
    print(f"Total tiles created: {total_tiles} across {len(target_scenes)} scenes")
    print(f"Location: {out_dir}")
    print(f"=======================================================")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Prepare Zenodo Sentinel-1 Dataset")
    parser.add_argument("--scenes", nargs="+", default=["00642", "00643", "00644", "00646"], help="Scene IDs to ingest")
    parser.add_argument("--tile-size", type=int, default=128, help="Tile size in pixels")
    args = parser.parse_args()

    prepare_zenodo_dataset(target_scenes=args.scenes, tile_size=args.tile_size)
