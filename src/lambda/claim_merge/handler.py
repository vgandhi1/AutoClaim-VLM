"""Merge enrichment + VLM output into final claim record for downstream loaders."""

from __future__ import annotations

import json
import logging

logger = logging.getLogger(__name__)


def handler(event: dict, context: object) -> dict:
    payload = json.loads(event["body"]) if isinstance(event.get("body"), str) else event
    merged = {
        "claim_id": payload.get("claim_id"),
        "vlm": payload.get("vlm", {}),
        "enrichment": payload.get("enrichment", {}),
    }
    return {"statusCode": 200, "body": json.dumps(merged)}
