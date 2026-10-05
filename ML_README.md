# AEGIS-SPILL: Machine Learning Oil Spill Detection & Segmentation Pipeline

## 📌 Overview

The **AEGIS-SPILL ML Pipeline** is a modular, high-performance PyTorch system designed for pixel-level oil spill detection and segmentation from Sentinel-1 Synthetic Aperture Radar (SAR) and multimodal satellite imagery.

It fulfills the detection baseline requirements of **SIH PS26143**, providing the geometric and spatial slick segmentations that feed directly into downstream reverse-Lagrangian hindcasting, AIS impossible-vessel filtering, and counterfactual forensics.

---

## 👥 Team Work Allocation & Responsibilities

In alignment with the **Model Training Team Implementation Plan (Reya • Niharika • Riya)**:

| Member | Responsibility | Dataset Target | Key Deliverable | Critical Rule |
| :--- | :--- | :--- | :--- | :--- |
| **Reya** | Baseline & Shared Training Pipeline | 23-scene Gulf of Mexico Sentinel-1 dataset | PyTorch U-Net baseline, data contract, checkpointing, loss functions | Master reference model; zero test leakage. |
| **Niharika** | Large-Scale SAR Training & Transfer Learning | Zenodo Part I (1,200 oil-spill images + masks) | Fine-tuned U-Net & pretrained encoder comparisons | Strict adherence to the shared preprocessing contract. |
| **Riya** | Look-Alike Robustness & Held-Out Testing | Zenodo Part II (685 look-alike + 685 clean) & Part III (150 oil + 150 look-alike + 150 clean) | False-positive analysis, confusion matrices, frozen test benchmark | Part III is completely held-out; never train or tune on Part III. |

---

## 📂 Architecture & Directory Layout

```
ml/
├── __init__.py               # Package metadata
├── config.py                 # Central configuration (paths, hyperparameters, seeds)
├── run_pipeline.py           # Unified CLI orchestrator (inspect, train, eval, predict)
├── create_smoke_dataset.py   # Synthetic SAR multi-scene dataset generator for smoke tests
├── data/
│   ├── __init__.py
│   ├── dataset.py            # OilSpillDataset & scene-aware train/val/test splitting
│   └── preprocessing.py      # Synchronized spatial augmentations & normalization
├── models/
│   ├── __init__.py
│   └── model.py              # SARUNet PyTorch architecture (double convs, skips, logits/probs)
├── training/
│   ├── __init__.py
│   ├── losses.py             # Combined BCE + Soft Dice Loss for extreme class imbalance
│   └── train.py              # Training loop with early stopping, scheduler, checkpointing
├── evaluation/
│   ├── __init__.py
│   └── evaluate.py           # Metrics computation, confusion matrix, 4-panel visual overlays
├── inference/
│   ├── __init__.py
│   └── predict.py            # High-speed cached singleton inference engine
└── utils/
    ├── __init__.py
    └── metrics.py            # IoU (Jaccard), Dice (F1), Precision, Recall, Pixel Accuracy

models/
├── best_model.pth            # Best checkpoint state_dict and training metadata
└── model_config.json         # Architectural and inference parameters

outputs/
├── training_metrics.json     # Epoch-by-epoch loss and validation metrics history
├── test_evaluation_metrics.json  # Held-out test split evaluation
├── predictions/              # Predicted masks (.png & .npy) and detection overlays
└── visualizations/           # 4-panel comparison strips and training curves
```

---

## 🛰️ Dataset Format & Ingestion Contract

The data loader automatically discovers and pairs satellite images and masks across both NumPy `.npy` arrays and standard image formats (`.png`, `.jpg`, `.tif`).

### Expected Directory Structure
```
datasets/
├── images/
│   ├── scene_01_tile_01.png (or .npy)
│   ├── scene_01_tile_02.png
│   └── scene_02_tile_01.png
└── masks/
    ├── scene_01_tile_01_mask.png (or .npy)
    ├── scene_01_tile_02_mask.png
    └── scene_02_tile_01_mask.png
```

### Preprocessing Specifications
- **Input Channels**: Single-channel SAR backscatter ($1 \times H \times W$) or 3-channel optical RGB.
- **Normalization**: Pixel values scaled to $[0, 1]$, standardized with $\mu = 0.5, \sigma = 0.5$.
- **Target Spatial Size**: $128 \times 128$ (configurable to $256 \times 256$ in `config.py`).
- **Binary Mask Convention**: $1$ = Oil Slick / Dark Patch; $0$ = Background Sea Clutter / Look-alike.
- **Synchronized Data Augmentation (Training Only)**: Random horizontal flip ($p=0.5$), vertical flip ($p=0.5$), and $90^\circ$ rotations applied simultaneously to both image and mask. Zero augmentation leakage into validation or test splits.
- **Scene-Aware Splitting**: Samples sharing scene prefixes (e.g., `scene_01_*`) are grouped into the same split to avoid geographic autocorrelation leakage.

---

## 🧠 Model Architecture & Loss Function

### SAR U-Net
- **Encoder**: 3-level convolutional hierarchy `[32, 64, 128]` with double convolutions, Batch Normalization, and Dropout ($p=0.1$).
- **Skip Connections**: Concatenates high-resolution spatial feature maps from the encoder to the decoder to preserve crisp oil slick boundaries.
- **Decoder**: Transposed convolutions followed by double convolutions.
- **Classifier Head**: $1 \times 1$ convolution outputting raw logits for numerical stability during training, and sigmoid probabilities during inference.
- **Lightweight Efficiency**: $\approx 1.9\text{M}$ parameters, allowing fast CPU execution ($< 25\text{ms}$ per tile).

### Hybrid Objective: Combined BCE + Soft Dice Loss
$$\mathcal{L}_{\text{total}} = 0.5 \cdot \mathcal{L}_{\text{BCEWithLogits}} + 0.5 \cdot \mathcal{L}_{\text{SoftDice}}$$

**Why this loss function?**
- Marine oil spills occupy $< 5\%$ of satellite scene pixels (severe class imbalance).
- Binary Cross-Entropy (BCE) alone causes the network to collapse to predicting all background pixels ($0$).
- Soft Dice Loss directly optimizes the overlap (Intersection over Union), heavily penalizing missed slick pixels (false negatives).
- BCE provides smooth gradients in early training iterations.

---

## 🚀 Commands & Usage

All commands can be run using the backend Python environment:

```powershell
# In project root:
$PYTHON = ".\backend\.venv\Scripts\python.exe"
```

### 1. Inspect Dataset
```powershell
& $PYTHON -m ml.run_pipeline --inspect
```
Outputs total images, masks, dimensions, missing samples, and class pixel distributions.

### 2. Generate Smoke Dataset (Pipeline Verification)
```powershell
& $PYTHON -m ml.run_pipeline --create-smoke-data
```

### 3. Train Model
```powershell
& $PYTHON -m ml.run_pipeline --train --epochs 10 --batch-size 4 --lr 1e-3
```
- Performs validation after every epoch.
- Checkpoints best model to `models/best_model.pth`.
- Saves configuration to `models/model_config.json`.
- Logs training curves and metrics to `outputs/training_metrics.json`.

### 4. Evaluate Held-Out Test Set
```powershell
& $PYTHON -m ml.run_pipeline --evaluate
```
Calculates:
- Intersection over Union (IoU)
- Dice / F1 Score
- Precision & Recall
- Pixel Accuracy & Specificity
- Confusion Matrix (TP, FP, TN, FN)
- Generates 4-panel visual strips: `[Original | Ground Truth | Prediction | Red Overlay]`.

### 5. Run Standalone Inference
```powershell
& $PYTHON -m ml.run_pipeline --predict backend/test_sar.npy
```

---

## 🌐 FastAPI REST Integration

The model is natively integrated into the existing FastAPI backend.

### Endpoints
- `POST /predict` (Root path)
- `POST /api/v1/predict` (API Prefix path)

### Request
Multipart form upload with an image file:
- **Field**: `file` (`.png`, `.jpg`, `.jpeg`, `.tif`, `.npy`)
- **Query Parameter (Optional)**: `threshold=0.5`

### Sample Response (`HTTP 200 OK`)
```json
{
  "oil_spill_detected": true,
  "confidence": 0.512,
  "spill_area_pixels": 16384,
  "total_pixels": 16384,
  "spill_ratio": 1.0,
  "threshold": 0.5,
  "mask_path": "outputs/predictions/test_sar_0e9e5af1_mask.png",
  "overlay_path": "outputs/predictions/test_sar_0e9e5af1_overlay.png",
  "model_version": "v1.0.0-sar-unet",
  "input_resolution": [128, 128],
  "processed_resolution": [128, 128]
}
```

### Performance & Safety
- **Model Singleton**: The model is loaded into memory once on startup and reused across requests.
- **Validation**: Rejects non-image extensions with descriptive `HTTP 400 Bad Request`.
- **CORS**: Preserved for seamless integration with the React WebGIS frontend.

---

## ⚠️ Limitations & Future Improvements

1. **Hardware**: Currently running in automatic CPU fallback mode (`torch.cuda.is_available() == False`). CUDA acceleration will automatically activate when deployed on a GPU instance.
2. **Benchmark Data Pending**: The 23-scene Gulf of Mexico dataset and Zenodo Parts I-III should be placed in `ml/datasets/` to execute real-world large-scale training and frozen held-out benchmarking.
3. **Multimodal Look-Alike Disambiguation**: Future integration with Sentinel-2 RGB/NIR and thermal infrared (TIR) via SegFormer to distinguish biogenic slicks and low-wind areas.
