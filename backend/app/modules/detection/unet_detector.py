import torch
import torch.nn as nn
import numpy as np
from typing import Tuple, Dict, Any

class DoubleConv(nn.Module):
    """(Convolution => [BN] => ReLU) * 2"""
    def __init__(self, in_channels: int, out_channels: int):
        super().__init__()
        self.net = nn.Sequential(
            nn.Conv2d(in_channels, out_channels, kernel_size=3, padding=1),
            nn.BatchNorm2d(out_channels),
            nn.ReLU(inplace=True),
            nn.Conv2d(out_channels, out_channels, kernel_size=3, padding=1),
            nn.BatchNorm2d(out_channels),
            nn.ReLU(inplace=True)
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x)

class SARUNetBaseline(nn.Module):
    """
    Lightweight SAR U-Net Baseline Architecture for Marine Slick Dark Patch Segmentation.
    Follows Alva & Rodriguez (2024) and Dong et al. (2025) SAR U-Net guidelines.
    """
    def __init__(self, in_channels: int = 1, out_channels: int = 1, features: list = [32, 64, 128]):
        super().__init__()
        self.downs = nn.ModuleList()
        self.ups = nn.ModuleList()
        self.pool = nn.MaxPool2d(kernel_size=2, stride=2)
        
        # Downsampling path
        in_c = in_channels
        for feature in features:
            self.downs.append(DoubleConv(in_c, feature))
            in_c = feature
            
        # Bottleneck
        self.bottleneck = DoubleConv(features[-1], features[-1] * 2)
        
        # Upsampling path
        for feature in reversed(features):
            self.ups.append(
                nn.ConvTranspose2d(feature * 2, feature, kernel_size=2, stride=2)
            )
            self.ups.append(DoubleConv(feature * 2, feature))
            
        self.final_conv = nn.Conv2d(features[0], out_channels, kernel_size=1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        skip_connections = []
        for down in self.downs:
            x = down(x)
            skip_connections.append(x)
            x = self.pool(x)
            
        x = self.bottleneck(x)
        skip_connections = skip_connections[::-1]
        
        for idx in range(0, len(self.ups), 2):
            x = self.ups[idx](x)
            skip_connection = skip_connections[idx // 2]
            concat_x = torch.cat((skip_connection, x), dim=1)
            x = self.ups[idx + 1](concat_x)
            
        return torch.sigmoid(self.final_conv(x))

_CACHED_DETECTOR_MODEL = None

def get_sar_detector_model() -> nn.Module:
    """Loads and caches SAR U-Net detector with trained weights if available."""
    global _CACHED_DETECTOR_MODEL
    if _CACHED_DETECTOR_MODEL is not None:
        return _CACHED_DETECTOR_MODEL

    model = SARUNetBaseline(in_channels=1, out_channels=1)
    
    # Check possible checkpoint paths
    from pathlib import Path
    candidate_paths = [
        Path(__file__).resolve().parent.parent.parent.parent.parent / "models" / "best_model.pth",
        Path("models/best_model.pth"),
        Path("../models/best_model.pth"),
    ]
    ckpt_path = next((p for p in candidate_paths if p.exists()), None)
    if ckpt_path:
        try:
            checkpoint = torch.load(ckpt_path, map_location="cpu")
            state_dict = checkpoint.get("model_state_dict", checkpoint)
            model.load_state_dict(state_dict, strict=False)
            print(f"[AEGIS-SPILL Detection] Loaded weights from {ckpt_path}")
        except Exception as e:
            print(f"[AEGIS-SPILL Detection] Failed to load checkpoint: {e}")

    model.eval()
    _CACHED_DETECTOR_MODEL = model
    return _CACHED_DETECTOR_MODEL


def run_sar_segmentation(image_array: np.ndarray, threshold: float = 0.5) -> np.ndarray:
    """
    Executes inference using the SAR U-Net baseline on a normalized SAR tile.
    Returns binary segmentation mask (1=Oil/Dark Patch, 0=Background Sea).
    """
    model = get_sar_detector_model()
    
    # Preprocess image array (ensure shape is [1, 1, H, W])
    if len(image_array.shape) == 2:
        tensor_in = torch.from_numpy(image_array).float().unsqueeze(0).unsqueeze(0)
    elif len(image_array.shape) == 3:
        tensor_in = torch.from_numpy(image_array[:, :, 0]).float().unsqueeze(0).unsqueeze(0)
    else:
        tensor_in = torch.from_numpy(image_array).float()
        
    with torch.no_grad():
        prob_map = model(tensor_in).squeeze().cpu().numpy()
        
    mask = (prob_map >= threshold).astype(np.uint8)
    return mask
