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


CARDD_ANNOTATION_KEYS = (
    "cardd/CarDD-SI-main/annotations/instances_train.json",
    "cardd/CarDD-SI-main/annotations/instances_val.json",
)


def _bbox_to_zones(bbox: list[float], img_w: float, img_h: float) -> list[str]:
    """Map a COCO bbox center to a coarse 3x3 spatial grid zone.

    Derived purely from the annotation geometry — far more informative than the
    previous unconditional ["full_body"] fallback.
    """
    if not bbox or not img_w or not img_h:
        return ["full_body"]
    x, y, w, h = bbox[0], bbox[1], bbox[2], bbox[3]
    cx = (x + w / 2.0) / img_w
    cy = (y + h / 2.0) / img_h
    col = "left" if cx < 1 / 3 else ("right" if cx > 2 / 3 else "center")
    row = "top" if cy < 1 / 3 else ("bottom" if cy > 2 / 3 else "mid")
    return [f"{row}_{col}"]


def build_cardd_manifest_from_s3(bucket: str, s3_client: Any) -> int:
    records: list[dict[str, Any]] = []
    seen_ann_ids: set[int] = set()

    for ann_key in CARDD_ANNOTATION_KEYS:
        try:
            ann_obj = s3_client.get_object(Bucket=bucket, Key=ann_key)
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code", "")
            if code in ("404", "NoSuchKey"):
                logger.warning("Annotation key missing: %s", ann_key)
                continue
            raise
        coco = json.loads(ann_obj["Body"].read())

        cat_map = {c["id"]: c["name"] for c in coco["categories"]}
        img_map = {
            img["id"]: (img["file_name"], img.get("width", 0), img.get("height", 0))
            for img in coco["images"]
        }

        for ann in coco["annotations"]:
            ann_id = ann["id"]
            if ann_id in seen_ann_ids:
                continue
            seen_ann_ids.add(ann_id)
            img_file, img_w, img_h = img_map[ann["image_id"]]
            cat_name = cat_map[ann["category_id"]]
            bbox = ann["bbox"]
            records.append(
                {
                    "source_dataset": "cardd",
                    "image_s3_key": f"cardd/CarDD-SI-main/images/{img_file}",
                    "category_name": cat_name,
                    "bbox": bbox,
                    "segmentation": ann.get("segmentation", []),
                    "area": ann["area"],
                    "annotation_id": ann_id,
                    "inferred_zones": _bbox_to_zones(bbox, img_w, img_h),
                }
            )

    if not records:
        return 0

    manifest = "\n".join(json.dumps(r) for r in records)
    s3_client.put_object(Bucket=bucket, Key="cardd/manifest.jsonl", Body=manifest.encode("utf-8"))
    return len(records)


def run_cardd_ingest(bucket: str, s3_client: Any) -> dict[str, Any]:
    logger.info("Downloading CarDD archive")
    data = download_cardd_zip()
    upload_zip_entries_to_s3(data, bucket, "cardd/", s3_client)
    count = build_cardd_manifest_from_s3(bucket, s3_client)
    return {"status": "ok", "records": count}
