"""Stream images from curated HuggingFace datasets into S3."""

from __future__ import annotations

import json
import logging
import os
from io import BytesIO
from typing import Any

from PIL import Image

logger = logging.getLogger(__name__)

HF_DATASETS: tuple[dict[str, str], ...] = (
    {
        "name": "keremberke/vehicle-damage-detection",
        "split": "train",
        "s3_prefix": "huggingface_vdd",
        "image_col": "image",
        "label_col": "objects",
    },
)


def _extract_vdd_label(example: dict, label_col: str) -> str:
    objs = example.get(label_col)
    if isinstance(objs, dict):
        lab = objs.get("label", ["damage"])
        if isinstance(lab, (list, tuple)) and lab:
            return str(lab[0])
        return str(lab) if lab is not None else "damage"
    return "damage"


def run_huggingface_ingest(
    bucket: str,
    s3_client: Any,
    max_rows: int | None = None,
) -> dict[str, int]:
    from datasets import load_dataset

    counts: dict[str, int] = {}
    limit_env = os.environ.get("HF_INGEST_MAX_ROWS")
    limit = max_rows if max_rows is not None else (int(limit_env) if limit_env else None)

    for ds_config in HF_DATASETS:
        logger.info("Loading dataset %s", ds_config["name"])
        dataset = load_dataset(ds_config["name"], split=ds_config["split"])
        records: list[dict[str, Any]] = []

        for i, example in enumerate(dataset):
            if limit is not None and i >= limit:
                break
            img: Image.Image = example[ds_config["image_col"]]
            buf = BytesIO()
            img.convert("RGB").save(buf, format="JPEG", quality=90)
            buf.seek(0)
            s3_key = f"{ds_config['s3_prefix']}/{i:06d}.jpg"
            s3_client.put_object(
                Bucket=bucket,
                Key=s3_key,
                Body=buf.read(),
                ContentType="image/jpeg",
            )
            label = _extract_vdd_label(example, ds_config["label_col"])
            records.append(
                {
                    "source_dataset": ds_config["s3_prefix"],
                    "image_s3_key": s3_key,
                    "label": label,
                    "index": i,
                }
            )

        manifest = "\n".join(json.dumps(r) for r in records)
        s3_client.put_object(
            Bucket=bucket,
            Key=f"{ds_config['s3_prefix']}/manifest.jsonl",
            Body=manifest.encode("utf-8"),
        )
        counts[ds_config["name"]] = len(records)
    return counts
