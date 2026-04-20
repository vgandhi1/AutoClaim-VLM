"""S3 object-created trigger: enqueue claim processing work (SQS)."""

from __future__ import annotations

import json
import logging
import os
import urllib.parse

import boto3

logger = logging.getLogger(__name__)
sqs = boto3.client("sqs")


def handler(event: dict, context: object) -> dict:
    queue_url = os.environ["INGEST_QUEUE_URL"]
    records_out = 0
    for record in event.get("Records", []):
        if record.get("eventSource") != "aws:s3":
            continue
        bucket = record["s3"]["bucket"]["name"]
        raw_key = urllib.parse.unquote_plus(record["s3"]["object"]["key"])
        if not raw_key.startswith("claims/"):
            continue
        body = json.dumps({"bucket": bucket, "raw_key": raw_key})
        sqs.send_message(QueueUrl=queue_url, MessageBody=body)
        records_out += 1
    return {"ok": True, "enqueued": records_out}
