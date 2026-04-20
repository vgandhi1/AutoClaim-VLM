from io import BytesIO

import boto3
import numpy as np
from moto import mock_aws
from PIL import Image

from glue.opensource_consolidation import process_manifest_row


@mock_aws
def test_process_manifest_row_ok():
    raw_bucket = "raw-bucket"
    processed_bucket = "out-bucket"
    s3 = boto3.client("s3", region_name="us-east-1")
    s3.create_bucket(Bucket=raw_bucket)
    s3.create_bucket(Bucket=processed_bucket)

    rng = np.random.default_rng(0)
    arr = (rng.random((400, 400, 3)) * 255).astype(np.uint8)
    img = Image.fromarray(arr, mode="RGB")
    buf = BytesIO()
    img.save(buf, format="JPEG", quality=95)
    body = buf.getvalue()

    key = "kaggle_car_damage/02-moderate/sample.jpg"
    s3.put_object(Bucket=raw_bucket, Key=key, Body=body, ContentType="image/jpeg")

    row = {
        "source_dataset": "kaggle_car_damage",
        "image_s3_key": key,
        "severity_folder": "02-moderate",
    }
    result = process_manifest_row(row, raw_bucket, processed_bucket, s3)
    assert result["status"] == "ok"
    assert result["damage_severity"] == "MODERATE"
    assert result["processed_s3_key"].startswith("kaggle_car_damage/")
    out = s3.get_object(Bucket=processed_bucket, Key=result["processed_s3_key"])
    assert out["ContentLength"] > 0
