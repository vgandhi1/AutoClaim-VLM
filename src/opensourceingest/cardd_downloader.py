"""Download CarDD-SI from the official GitHub archive (fixed URL) and build manifest."""

from __future__ import annotations

import io
import json
import logging
import zipfile
from typing import Any

import requests
from botocore.exceptions import ClientError

from opensourceingest.pathutil import is_safe_zip_member

logger = logging.getLogger(__name__)

CARDD_ZIP_URL = (
    "https://github.com/CarDD-USTB/CarDD-SI/archive/refs/heads/main.zip"
)


def download_cardd_zip(timeout: int = 600) -> bytes:
    resp = requests.get(CARDD_ZIP_URL, stream=True, timeout=timeout)
    resp.raise_for_status()
    return resp.content


def upload_zip_entries_to_s3(
    zip_bytes: bytes,
    bucket: str,
    prefix: str,
    s3_client: Any,
) -> None:
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        for entry in zf.namelist():
            if not is_safe_zip_member(entry):
                continue
            if not (entry.endswith(".jpg") or entry.endswith(".json")):
                continue
            key = f"{prefix}{entry}"
            s3_client.put_object(Bucket=bucket, Key=key, Body=zf.read(entry))


def build_cardd_manifest_from_s3(bucket: str, s3_client: Any) -> int:
    ann_key = "cardd/CarDD-SI-main/annotations/instances_train.json"
    try:
        ann_obj = s3_client.get_object(Bucket=bucket, Key=ann_key)
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code", "")
        if code in ("404", "NoSuchKey"):
            logger.warning("Annotation key missing: %s", ann_key)
            return 0
        raise
    coco = json.loads(ann_obj["Body"].read())

    cat_map = {c["id"]: c["name"] for c in coco["categories"]}
    img_map = {img["id"]: img["file_name"] for img in coco["images"]}
    records: list[dict[str, Any]] = []

    for ann in coco["annotations"]:
        img_file = img_map[ann["image_id"]]
        cat_name = cat_map[ann["category_id"]]
        records.append(
            {
                "source_dataset": "cardd",
                "image_s3_key": f"cardd/CarDD-SI-main/images/{img_file}",
                "category_name": cat_name,
                "bbox": ann["bbox"],
                "segmentation": ann.get("segmentation", []),
                "area": ann["area"],
                "annotation_id": ann["id"],
            }
        )

    manifest = "\n".join(json.dumps(r) for r in records)
    s3_client.put_object(Bucket=bucket, Key="cardd/manifest.jsonl", Body=manifest.encode("utf-8"))
    return len(records)


def run_cardd_ingest(bucket: str, s3_client: Any) -> dict[str, Any]:
    logger.info("Downloading CarDD archive")
    data = download_cardd_zip()
    upload_zip_entries_to_s3(data, bucket, "cardd/", s3_client)
    count = build_cardd_manifest_from_s3(bucket, s3_client)
    return {"status": "ok", "records": count}
