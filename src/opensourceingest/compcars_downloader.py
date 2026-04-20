"""CompCars archive download, MATLAB label parsing, and optional S3 upload."""

from __future__ import annotations

import json
import logging
import os
import tarfile
from pathlib import Path
from typing import Any

from PIL import Image
from tqdm import tqdm

logger = logging.getLogger(__name__)


def load_make_model_lookup(mat_path: str | Path) -> dict[tuple[int, int], dict[str, str]]:
    import scipy.io as sio

    mat = sio.loadmat(str(mat_path))
    makes = [str(m[0]) for m in mat["make_names"].flatten()]
    lookup: dict[tuple[int, int], dict[str, str]] = {}
    for i, model_list in enumerate(mat["model_names"].flatten(), start=1):
        for j, model_name in enumerate(model_list.flatten(), start=1):
            lookup[(i, j)] = {
                "make": makes[i - 1],
                "model": str(model_name[0]) if getattr(model_name, "size", 0) > 0 else "Unknown",
            }
    return lookup


def download_archive(gdrive_file_id: str, dest_path: Path) -> None:
    import gdown

    dest_path.parent.mkdir(parents=True, exist_ok=True)
    url = f"https://drive.google.com/uc?id={gdrive_file_id}"
    gdown.download(url, str(dest_path), quiet=False)


def extract_tar_gz(archive: Path, dest_dir: Path) -> None:
    dest_dir.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive, "r:gz") as tar:
        tar.extractall(dest_dir)


def iter_compcars_records(
    local_root: Path,
    label_lookup: dict[tuple[int, int], dict[str, str]],
    min_side: int = 200,
) -> list[dict[str, Any]]:
    image_root = local_root / "data" / "image"
    records: list[dict[str, Any]] = []
    if not image_root.exists():
        return records

    for img_path in image_root.rglob("*.jpg"):
        try:
            rel = img_path.relative_to(image_root)
        except ValueError:
            continue
        parts = rel.parts
        if len(parts) < 4:
            continue
        try:
            make_id = int(parts[0])
            model_id = int(parts[1])
            year = parts[2]
            part_id = int(parts[3])
        except ValueError:
            continue

        label_info = label_lookup.get((make_id, model_id), {"make": "Unknown", "model": "Unknown"})
        try:
            img = Image.open(img_path)
            w, h = img.size
            if w < min_side or h < min_side:
                continue
        except OSError:
            continue

        s3_key = f"compcars/web/{make_id}/{model_id}/{year}/{part_id}/{img_path.name}"
        records.append(
            {
                "source_dataset": "compcars",
                "image_s3_key": s3_key,
                "make_id": make_id,
                "model_id": model_id,
                "year": year,
                "part_id": part_id,
                "make": label_info["make"],
                "model": label_info["model"],
            }
        )
    return records


def upload_records_to_s3(
    records: list[dict[str, Any]],
    local_root: Path,
    bucket: str,
    s3_client: Any,
) -> None:
    image_root = local_root / "data" / "image"
    for rec in tqdm(records, desc="Uploading CompCars"):
        key = rec["image_s3_key"]
        rel = Path(key.replace("compcars/web/", ""))
        local_file = image_root / rel
        if local_file.exists():
            s3_client.upload_file(str(local_file), bucket, key)

    manifest = "\n".join(json.dumps(r) for r in records)
    s3_client.put_object(Bucket=bucket, Key="compcars/manifest.jsonl", Body=manifest.encode("utf-8"))
    logger.info("Uploaded CompCars manifest with %s records", len(records))


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    bucket = os.environ.get("CLAIMLENS_RAW_BUCKET", "vehicle-damage-opensource-raw")
    gdrive_id = os.environ.get("COMPCARS_GDRIVE_FILE_ID")
    local_root = Path(os.environ.get("COMPCARS_LOCAL_ROOT", "/tmp/compcars"))

    if not gdrive_id:
        logger.error("Set COMPCARS_GDRIVE_FILE_ID to the registered CompCars archive id")
        raise SystemExit(2)

    archive = local_root / "compcars.tar.gz"
    download_archive(gdrive_id, archive)
    extract_tar_gz(archive, local_root)

    mat = local_root / "data" / "misc" / "make_model_name.mat"
    if not mat.exists():
        logger.error("Expected make_model_name.mat at %s", mat)
        raise SystemExit(1)

    lookup = load_make_model_lookup(mat)
    records = iter_compcars_records(local_root, lookup)

    import boto3

    s3 = boto3.client("s3")
    upload_records_to_s3(records, local_root, bucket, s3)


if __name__ == "__main__":  # pragma: no cover
    main()
