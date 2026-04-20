"""
AWS Glue job: operational claim images → QA + 640×640 JPEG on the processed bucket.

Wire Spark/DynamicFrame mapping in Terraform (input manifests, output paths).

Local smoke test:
  PYTHONPATH=src python src/glue/vehicle_damage_preprocess.py --local
"""

from __future__ import annotations

import json
import logging
import os
import sys

import boto3

from claimlens.processing import preprocess_claim_image

logger = logging.getLogger(__name__)


def run_local_example() -> None:
    raw_bucket = os.environ.get("CLAIMLENS_RAW_BUCKET", "claimlens-raw-dev")
    processed_bucket = os.environ.get("CLAIMLENS_PROCESSED_BUCKET", "claimlens-processed-dev")
    key = os.environ.get("CLAIMLENS_SAMPLE_KEY", "claims/sample.jpg")
    s3 = boto3.client("s3")
    result = preprocess_claim_image(raw_bucket, key, processed_bucket, s3)
    print(json.dumps(result))


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    if "--local" in sys.argv:
        run_local_example()
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
        "vehicle_damage_preprocess initialized (raw=%s processed=%s). "
        "Attach DynamicFrame sources in Terraform before production runs.",
        args["RAW_BUCKET"],
        args["PROCESSED_BUCKET"],
    )
    job.commit()


if __name__ == "__main__":  # pragma: no cover
    main()
