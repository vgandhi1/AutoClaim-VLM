"""Image QA helpers: blur score (Laplacian variance), perceptual hash, resize."""

from __future__ import annotations

from io import BytesIO
from typing import Tuple

import numpy as np
from PIL import Image
from scipy.ndimage import convolve


def laplacian_blur_score_gray(gray: np.ndarray) -> float:
    """Variance of Laplacian on grayscale image (higher = sharper)."""
    lap = np.array([[0.0, 1.0, 0.0], [1.0, -4.0, 1.0], [0.0, 1.0, 0.0]], dtype=np.float64)
    if gray.shape[0] < 3 or gray.shape[1] < 3:
        return 0.0
    filtered = convolve(gray, lap, mode="nearest")
    return float(np.var(filtered))


def blur_score_rgb(img: Image.Image) -> float:
    arr = np.asarray(img.convert("RGB"), dtype=np.float64)
    gray = np.mean(arr, axis=2)
    return laplacian_blur_score_gray(gray)


def brightness_mean_rgb(img: Image.Image) -> float:
    arr = np.asarray(img.convert("RGB"), dtype=np.float64)
    return float(np.mean(arr))


def perceptual_hash_bits(img: Image.Image, size: int = 8) -> str:
    small = img.resize((size, size), Image.Resampling.LANCZOS).convert("L")
    pixels = list(small.getdata())
    avg = sum(pixels) / len(pixels)
    return "".join("1" if p > avg else "0" for p in pixels)


def phash_hamming(hash1: str, hash2: str) -> int:
    if len(hash1) != len(hash2):
        return 64
    return sum(c1 != c2 for c1, c2 in zip(hash1, hash2))


def resize_square_jpeg(img: Image.Image, side: int = 640, quality: int = 88) -> bytes:
    rgb = img.convert("RGB")
    out = rgb.resize((side, side), Image.Resampling.LANCZOS)
    buf = BytesIO()
    out.save(buf, format="JPEG", quality=quality)
    return buf.getvalue()


def passes_quality_gates(
    img: Image.Image,
    min_side: int = 224,
    min_blur: float = 50.0,
) -> Tuple[bool, str, dict[str, float | int]]:
    w, h = img.size
    if w < min_side or h < min_side:
        return False, "resolution_too_low", {"resolution_w": w, "resolution_h": h}

    blur = blur_score_rgb(img)
    if blur < min_blur:
        return False, "image_too_blurry", {"blur_score": blur, "resolution_w": w, "resolution_h": h}

    bright = brightness_mean_rgb(img)
    return True, "ok", {"blur_score": blur, "brightness_mean": bright, "resolution_w": w, "resolution_h": h}
