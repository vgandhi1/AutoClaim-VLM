"""Operational claim image preprocessing (resize, QA, fingerprint)."""

from __future__ import annotations

import json
from io import BytesIO
from typing import Any

from PIL import Image

from opensourceingest.image_quality import (
    passes_quality_gates,
    perceptual_hash_bits,
    resize_square_jpeg,
)


def preprocess_claim_image(
    raw_bucket: str,
    raw_key: str,
    processed_bucket: str,
    s3_client: Any,
    processed_prefix: str = "processed/claims/",
) -> dict[str, Any]:
    obj = s3_client.get_object(Bucket=raw_bucket, Key=raw_key)
    body = obj["Body"].read()
    img = Image.open(BytesIO(body)).convert("RGB")
    ok, reason, metrics = passes_quality_gates(img)
    phash = perceptual_hash_bits(img)
    relative = raw_key.split("claims/", 1)[-1] if "claims/" in raw_key else raw_key
    out_key = f"{processed_prefix}{relative}"

    if not ok:
        return {
            "status": "rejected",
            "reason": reason,
            "raw_key": raw_key,
            "phash_fingerprint": phash,
            **{k: v for k, v in metrics.items()},
        }

    jpeg = resize_square_jpeg(img, side=640, quality=88)
    s3_client.put_object(Bucket=processed_bucket, Key=out_key, Body=jpeg, ContentType="image/jpeg")
    return {
        "status": "ok",
        "raw_key": raw_key,
        "processed_key": out_key,
        "phash_fingerprint": phash,
        **{k: v for k, v in metrics.items()},
    }


def preprocess_claim_image_json_result(*args: Any, **kwargs: Any) -> str:
    return json.dumps(preprocess_claim_image(*args, **kwargs))
