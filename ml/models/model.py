"""
AEGIS-SPILL SAR U-Net Segmentation Model
Designed for high-accuracy, lightweight satellite oil spill segmentation.
Supports CPU and CUDA execution, flexible input channels, and numerical stability.
"""
from typing import List
import torch
import torch.nn as nn


class DoubleConv(nn.Module):
    """
    (Conv2d => BatchNorm2d => ReLU) * 2
    Preserves spatial dimensions via padding=1.
    """
    def __init__(self, in_channels: int, out_channels: int, dropout: float = 0.0):
        super().__init__()
        layers = [
            nn.Conv2d(in_channels, out_channels, kernel_size=3, padding=1, bias=False),
            nn.BatchNorm2d(out_channels),
            nn.ReLU(inplace=True),
            nn.Conv2d(out_channels, out_channels, kernel_size=3, padding=1, bias=False),
            nn.BatchNorm2d(out_channels),
            nn.ReLU(inplace=True),
        ]
        if dropout > 0.0:
            layers.append(nn.Dropout2d(p=dropout))
        self.net = nn.Sequential(*layers)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x)


class SARUNet(nn.Module):
    """
    PyTorch U-Net Architecture optimized for SAR & Optical Oil Slick Segmentation.
    Features:
    - Configurable depth and feature map dimensions.
    - Skip connections preserving fine-grained boundary edges.
    - Optional output activation: raw logits (default, for BCEWithLogitsLoss) or sigmoid probabilities.
    """
    def __init__(
        self,
        in_channels: int = 1,
        out_channels: int = 1,
        features: List[int] = [32, 64, 128],
        dropout: float = 0.1,
    ):
        super().__init__()
        self.in_channels = in_channels
        self.out_channels = out_channels
        self.features = features

        self.downs = nn.ModuleList()
        self.ups = nn.ModuleList()
        self.pool = nn.MaxPool2d(kernel_size=2, stride=2)

        # Encoder (Downsampling path)
        curr_in = in_channels
        for feat in features:
            self.downs.append(DoubleConv(curr_in, feat, dropout=dropout))
            curr_in = feat

        # Bottleneck
        self.bottleneck = DoubleConv(features[-1], features[-1] * 2, dropout=dropout)

        # Decoder (Upsampling path)
        for feat in reversed(features):
            self.ups.append(
                nn.ConvTranspose2d(feat * 2, feat, kernel_size=2, stride=2)
            )
            self.ups.append(DoubleConv(feat * 2, feat, dropout=dropout))

        # Output projection head (1x1 conv)
        self.final_conv = nn.Conv2d(features[0], out_channels, kernel_size=1)

    def forward(self, x: torch.Tensor, return_prob: bool = False) -> torch.Tensor:
        skip_connections = []

        # Encoder forward pass
        for down in self.downs:
            x = down(x)
            skip_connections.append(x)
            x = self.pool(x)

        # Bottleneck
        x = self.bottleneck(x)

        # Reverse skips for decoder
        skip_connections = skip_connections[::-1]

        # Decoder forward pass with skip connections
        for idx in range(0, len(self.ups), 2):
            x = self.ups[idx](x)
            skip_conn = skip_connections[idx // 2]
            
            # Handle possible slight shape mismatches if non-power-of-two dimensions
            if x.shape[2:] != skip_conn.shape[2:]:
                x = nn.functional.interpolate(x, size=skip_conn.shape[2:], mode="bilinear", align_corners=False)
                
            concat_x = torch.cat((skip_conn, x), dim=1)
            x = self.ups[idx + 1](concat_x)

        logits = self.final_conv(x)

        if return_prob:
            return torch.sigmoid(logits)
        return logits
