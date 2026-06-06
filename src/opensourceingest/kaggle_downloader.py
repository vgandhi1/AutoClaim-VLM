"""Kaggle dataset downloads using fixed dataset slugs (no user-controlled URLs)."""

from __future__ import annotations

import json
import logging
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

KAGGLE_DATASETS: tuple[dict[str, str], ...] = (
    {"slug": "anujms/car-damage-detector", "name": "kaggle_car_damage"},
    {"slug": "hendrichscullen/vehiface-dataset", "name": "kaggle_vehiface"},
)


def _require_kaggle_env() -> None:
    if not os.environ.get("KAGGLE_USERNAME") or not os.environ.get("KAGGLE_KEY"):
        raise RuntimeError("KAGGLE_USERNAME and KAGGLE_KEY must be set for Kaggle downloads")


def ingest_kaggle_dataset(ds: dict[str, str], bucket: str, s3_client: Any) -> int:
    _require_kaggle_env()
    with tempfile.TemporaryDirectory() as tmp:
        download_path = Path(tmp) / ds["name"]
        download_path.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            [
                "kaggle",
                "datasets",
                "download",
                ds["slug"],
                "-p",
                str(download_path),
                "--unzip",
            ],
            check=True,
            timeout=3600,
        )

        records: list[dict[str, Any]] = []
        image_paths = sorted(
            p
            for p in download_path.rglob("*")
            if p.suffix.lower() in {".jpg", ".jpeg", ".png"}
        )
        for img_path in image_paths:
            folder = img_path.parent.name
            s3_key = f"{ds['name']}/{folder}/{img_path.name}"
            s3_client.upload_file(str(img_path), bucket, s3_key)
            records.append(
                {
                    "source_dataset": ds["name"],
                    "image_s3_key": s3_key,
                    "severity_folder": folder,
                }
            )

        manifest = "\n".join(json.dumps(r) for r in records)
        s3_client.put_object(
            Bucket=bucket,
            Key=f"{ds['name']}/manifest.jsonl",
            Body=manifest.encode("utf-8"),
        )
        logger.info("%s: uploaded %s images", ds["name"], len(records))
        return len(records)


def run_kaggle_ingest(bucket: str, s3_client: Any) -> dict[str, int]:
    total: dict[str, int] = {}
    for ds in KAGGLE_DATASETS:
        total[ds["name"]] = ingest_kaggle_dataset(ds, bucket, s3_client)
    return total
