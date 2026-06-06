"""
AWS Glue job: consolidate open-source manifests into a normalized catalog.

`process_manifest_row` is the per-row worker used by Glue (mapPartitions) or tests.

Local:
  CLAIMLENS_RAW_BUCKET=... CLAIMLENS_PROCESSED_BUCKET=... \\
  PYTHONPATH=src python src/glue/opensource_consolidation.py --local-manifest path.jsonl
"""

from __future__ import annotations

import json
import logging
import os
import sys
from io import BytesIO
from typing import Any

import boto3
from botocore.exceptions import ClientError
from PIL import Image

from opensourceingest.image_quality import (
    passes_quality_gates,
    perceptual_hash_bits,
    resize_square_jpeg,
)
from opensourceingest.normalize import normalize_record

logger = logging.getLogger(__name__)


def process_manifest_row(
    raw: dict[str, Any],
    raw_bucket: str,
    processed_bucket: str,
    s3_client: Any,
    seen_phashes: set[str] | None = None,
) -> dict[str, Any]:
    source_dataset = raw.get("source_dataset", "unknown")
    image_key = raw["image_s3_key"]
    try:
        obj = s3_client.get_object(Bucket=raw_bucket, Key=image_key)
        img_bytes = obj["Body"].read()
        img = Image.open(BytesIO(img_bytes)).convert("RGB")
    except (ClientError, OSError, ValueError):
        return {"status": "error", "reason": "s3_read_failed", **raw}

    ok, reason, metrics = passes_quality_gates(img)
    phash = perceptual_hash_bits(img)
    if seen_phashes is not None:
        if phash in seen_phashes:
            return {"status": "rejected", "reason": "duplicate_phash", **raw, **metrics}
        seen_phashes.add(phash)
    if not ok:
        return {"status": "rejected", "reason": reason, **raw, **metrics}

    image_meta = {
        "make": raw.get("make"),
        "model": raw.get("model"),
        "year": raw.get("year"),
    }
    canonical = normalize_record(source_dataset, image_key, raw, image_meta)
    processed_key = f"{source_dataset}/{canonical['image_id']}.jpg"
    s3_client.put_object(
        Bucket=processed_bucket,
        Key=processed_key,
        Body=resize_square_jpeg(img),
        ContentType="image/jpeg",
    )

    return {
        **canonical,
        "status": "ok",
        "processed_s3_key": processed_key,
        "phash_fingerprint": phash,
        "blur_score": float(metrics.get("blur_score", 0.0)),
        "brightness_mean": float(metrics.get("brightness_mean", 0.0)),
        "resolution_w": int(metrics.get("resolution_w", 0)),
        "resolution_h": int(metrics.get("resolution_h", 0)),
    }


def run_local_manifest(manifest_path: str, raw_bucket: str, processed_bucket: str) -> None:
    s3 = boto3.client("s3")
    seen_phashes: set[str] = set()
    with open(manifest_path, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            result = process_manifest_row(
                row, raw_bucket, processed_bucket, s3, seen_phashes=seen_phashes
            )
            print(json.dumps(result))


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    if "--local-manifest" in sys.argv:
        idx = sys.argv.index("--local-manifest")
        path = sys.argv[idx + 1]
        raw_bucket = os.environ["CLAIMLENS_RAW_BUCKET"]
        processed_bucket = os.environ["CLAIMLENS_PROCESSED_BUCKET"]
        run_local_manifest(path, raw_bucket, processed_bucket)
        return

    try:
        from awsglue.context import GlueContext
        from awsglue.job import Job
        from awsglue.utils import getResolvedOptions
        from pyspark.context import SparkContext
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("Glue/Spark libraries are required on AWS Glue") from exc

    args = getResolvedOptions(
        sys.argv,
        ["JOB_NAME", "RAW_BUCKET", "PROCESSED_BUCKET"],
    )
    sc = SparkContext()
    glue_context = GlueContext(sc)
    job = Job(glue_context)
    job.init(args["JOB_NAME"], args)

    logger.info(
        "opensource_consolidation initialized (raw=%s processed=%s). "
        "Map manifests via Spark in Terraform for full runs.",
        args["RAW_BUCKET"],
        args["PROCESSED_BUCKET"],
    )
    job.commit()


if __name__ == "__main__":  # pragma: no cover
    main()
