"""Orchestrate open-source dataset downloads (CarDD, Kaggle, HuggingFace)."""

from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path
from typing import Any

import boto3

_SRC_ROOT = Path(__file__).resolve().parents[2]
if str(_SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(_SRC_ROOT))

logger = logging.getLogger(__name__)

ALLOWED = frozenset({"cardd", "kaggle", "huggingface"})


def handler(event: dict, context: object) -> dict:
    bucket = os.environ["CLAIMLENS_RAW_BUCKET"]
    s3 = boto3.client("s3")
    requested = event.get("datasets") or []
    if not isinstance(requested, list):
        return {"statusCode": 400, "body": json.dumps({"error": "invalid_request"})}

    unknown = [d for d in requested if d not in ALLOWED]
    if unknown:
        return {"statusCode": 400, "body": json.dumps({"error": "unknown_dataset"})}

    results: dict[str, Any] = {}
    if "cardd" in requested:
        from opensourceingest.cardd_downloader import run_cardd_ingest

        results["cardd"] = run_cardd_ingest(bucket, s3)
    if "kaggle" in requested:
        from opensourceingest.kaggle_downloader import run_kaggle_ingest

        results["kaggle"] = run_kaggle_ingest(bucket, s3)
    if "huggingface" in requested:
        from opensourceingest.huggingface_downloader import run_huggingface_ingest

        max_rows_env = os.environ.get("HF_INGEST_MAX_ROWS")
        max_rows = int(max_rows_env) if max_rows_env else None
        results["huggingface"] = run_huggingface_ingest(bucket, s3, max_rows=max_rows)

    return {"statusCode": 200, "body": json.dumps({"ok": True, "results": results})}
