from io import BytesIO

import numpy as np
from PIL import Image

from opensourceingest.image_quality import (
    blur_score_rgb,
    passes_quality_gates,
    perceptual_hash_bits,
    phash_hamming,
    resize_square_jpeg,
)


def _solid_image(w: int, h: int, color: tuple[int, int, int]) -> Image.Image:
    arr = np.zeros((h, w, 3), dtype=np.uint8)
    arr[:, :] = color
    return Image.fromarray(arr, mode="RGB")


def test_phash_stable():
    img = _solid_image(64, 64, (120, 120, 120))
    h1 = perceptual_hash_bits(img)
    h2 = perceptual_hash_bits(img)
    assert h1 == h2
    assert phash_hamming(h1, h2) == 0


def test_resize_square_jpeg():
    img = _solid_image(100, 200, (10, 40, 90))
    data = resize_square_jpeg(img, side=640, quality=90)
    out = Image.open(BytesIO(data))
    assert out.size == (640, 640)


def test_blur_score_positive_on_edges():
    img = _solid_image(64, 64, (0, 255, 0))
    xs = np.linspace(0, 255, 64)
    arr = np.tile(xs, (64, 1)).astype(np.uint8)
    noisy = Image.fromarray(np.stack([arr, arr, arr], axis=2))
    assert blur_score_rgb(img) >= 0
    assert blur_score_rgb(noisy) > blur_score_rgb(_solid_image(64, 64, (10, 10, 10)))


def test_quality_gate_rejects_small():
    img = _solid_image(50, 50, (200, 200, 200))
    ok, reason, _metrics = passes_quality_gates(img, min_side=224)
    assert ok is False
    assert reason == "resolution_too_low"
