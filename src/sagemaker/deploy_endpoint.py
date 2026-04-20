"""Create SageMaker model + endpoint configuration (dry-run friendly)."""

from __future__ import annotations

import argparse
import json
import logging
import os

import boto3

logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--model-id", dest="model_id", default="google/paligemma-3b-pt-448")
    p.add_argument("--model-artifact", dest="model_artifact", default="")
    p.add_argument("--env", default="dev")
    p.add_argument("--dry-run", action="store_true")
    return p.parse_args()


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    args = parse_args()
    region = os.environ.get("AWS_REGION", "us-east-1")
    role = os.environ.get("SAGEMAKER_ROLE_ARN", "")
    image = os.environ.get(
        "SAGEMAKER_IMAGE_URI",
        f"763104351884.dkr.ecr.{region}.amazonaws.com/pytorch-inference:2.1.0-gpu-py310",
    )
    sm = boto3.client("sagemaker", region_name=region)
    model_name = f"claimlens-vlm-{args.env}"
    container = {
        "Image": image,
        "Environment": {"MODEL_ID": args.model_id},
    }
    if args.model_artifact:
        container["ModelDataUrl"] = args.model_artifact
    payload = {
        "ModelName": model_name,
        "PrimaryContainer": container,
        "ExecutionRoleArn": role or "arn:aws:iam::000000000000:role/placeholder",
    }
    if args.dry_run or not role:
        logger.info("Dry-run SageMaker create_model payload: %s", json.dumps(payload, default=str))
        return
    sm.create_model(**payload)
    logger.info("Created SageMaker model %s", model_name)


if __name__ == "__main__":  # pragma: no cover
    main()
