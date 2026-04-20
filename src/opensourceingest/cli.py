"""CLI entrypoint for local open-source ingestion tasks."""

from __future__ import annotations

import argparse
import logging
import os

logger = logging.getLogger(__name__)


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser(description="ClaimLens open-source ingestion")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("compcars", help="CompCars download + S3 upload (requires env vars)")

    p_cardd = sub.add_parser("cardd", help="Download CarDD and upload to S3")
    p_cardd.add_argument("--bucket", default=os.environ.get("CLAIMLENS_RAW_BUCKET"))

    p_kaggle = sub.add_parser("kaggle", help="Download fixed Kaggle datasets to S3")
    p_kaggle.add_argument("--bucket", default=os.environ.get("CLAIMLENS_RAW_BUCKET"))

    p_hf = sub.add_parser("huggingface", help="HF vehicle-damage-detection to S3")
    p_hf.add_argument("--bucket", default=os.environ.get("CLAIMLENS_RAW_BUCKET"))
    p_hf.add_argument("--max-rows", type=int, default=None)

    args = parser.parse_args()

    if args.command == "compcars":
        from opensourceingest.compcars_downloader import main as compcars_main

        compcars_main()
        return

    bucket = getattr(args, "bucket", None)
    if not bucket:
        raise SystemExit("Set --bucket or CLAIMLENS_RAW_BUCKET")

    import boto3

    s3 = boto3.client("s3")

    if args.command == "cardd":
        from opensourceingest.cardd_downloader import run_cardd_ingest

        logger.info("%s", run_cardd_ingest(bucket, s3))
    elif args.command == "kaggle":
        from opensourceingest.kaggle_downloader import run_kaggle_ingest

        logger.info("%s", run_kaggle_ingest(bucket, s3))
    elif args.command == "huggingface":
        from opensourceingest.huggingface_downloader import run_huggingface_ingest

        logger.info("%s", run_huggingface_ingest(bucket, s3, max_rows=args.max_rows))


if __name__ == "__main__":  # pragma: no cover
    main()
