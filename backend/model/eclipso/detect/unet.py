"""U-Net for oil-slick segmentation of Sentinel-1 SAR (PyTorch).

Input: 1 (VV) or 2 (VV, VH) channels of sigma0 in dB, normalised with
`normalise_db`. Output: per-pixel oil logit. Kept small (~1.9 M params at
base=16) so it trains on a laptop GPU in an evening and runs on CPU for demos.
"""
from __future__ import annotations

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

DB_MEAN = -16.0
DB_STD = 4.0


def normalise_db(db: np.ndarray) -> np.ndarray:
    x = (np.nan_to_num(db, nan=DB_MEAN) - DB_MEAN) / DB_STD
    return np.clip(x, -5, 5).astype(np.float32)


class ConvBlock(nn.Module):
    def __init__(self, cin, cout):
        super().__init__()
        self.net = nn.Sequential(
            nn.Conv2d(cin, cout, 3, padding=1, bias=False), nn.BatchNorm2d(cout), nn.ReLU(inplace=True),
            nn.Conv2d(cout, cout, 3, padding=1, bias=False), nn.BatchNorm2d(cout), nn.ReLU(inplace=True),
        )

    def forward(self, x):
        return self.net(x)


class UNet(nn.Module):
    def __init__(self, in_ch: int = 1, base: int = 16, depth: int = 4):
        super().__init__()
        chs = [base * 2 ** i for i in range(depth + 1)]
        self.downs = nn.ModuleList()
        c = in_ch
        for ch in chs[:-1]:
            self.downs.append(ConvBlock(c, ch))
            c = ch
        self.bottom = ConvBlock(chs[-2], chs[-1])
        self.ups = nn.ModuleList()
        self.up_convs = nn.ModuleList()
        for ch in reversed(chs[:-1]):
            self.ups.append(nn.ConvTranspose2d(ch * 2, ch, 2, stride=2))
            self.up_convs.append(ConvBlock(ch * 2, ch))
        self.head = nn.Conv2d(chs[0], 1, 1)
        self.stride = 2 ** depth

    def forward(self, x):
        skips = []
        for d in self.downs:
            x = d(x)
            skips.append(x)
            x = F.max_pool2d(x, 2)
        x = self.bottom(x)
        for up, conv, s in zip(self.ups, self.up_convs, reversed(skips)):
            x = up(x)
            x = conv(torch.cat([x, s], 1))
        return self.head(x)


def dice_bce_loss(logits, target, eps=1.0):
    bce = F.binary_cross_entropy_with_logits(logits, target)
    p = torch.sigmoid(logits)
    inter = (p * target).sum((1, 2, 3))
    dice = 1 - (2 * inter + eps) / (p.sum((1, 2, 3)) + target.sum((1, 2, 3)) + eps)
    return bce + dice.mean()


def load_model(weights_path, device="cpu") -> UNet:
    ckpt = torch.load(weights_path, map_location=device, weights_only=False)
    model = UNet(in_ch=ckpt.get("in_ch", 1), base=ckpt.get("base", 16), depth=ckpt.get("depth", 4))
    model.load_state_dict(ckpt["state_dict"])
    model.eval()
    return model


@torch.no_grad()
def predict_prob(model: UNet, db: np.ndarray, device="cpu", tile: int = 512, overlap: int = 64) -> np.ndarray:
    """Probability map for a full scene (H, W) or (C, H, W), tiled with overlap."""
    x = normalise_db(db)
    if x.ndim == 2:
        x = x[None]
    C, Hh, Ww = x.shape
    out = np.zeros((Hh, Ww), np.float32)
    cnt = np.zeros((Hh, Ww), np.float32)
    step = tile - overlap
    s = model.stride
    for r0 in range(0, max(Hh - overlap, 1), step):
        for c0 in range(0, max(Ww - overlap, 1), step):
            r1, c1 = min(r0 + tile, Hh), min(c0 + tile, Ww)
            patch = x[:, r0:r1, c0:c1]
            ph, pw = patch.shape[1:]
            PH, PW = -(-ph // s) * s, -(-pw // s) * s
            patch = np.pad(patch, ((0, 0), (0, PH - ph), (0, PW - pw)), mode="reflect")
            logits = model(torch.from_numpy(patch)[None].to(device))[0, 0, :ph, :pw]
            out[r0:r1, c0:c1] += torch.sigmoid(logits).cpu().numpy()
            cnt[r0:r1, c0:c1] += 1
    return out / np.maximum(cnt, 1)
