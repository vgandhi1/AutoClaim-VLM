"""Post-VLM enrichment placeholder (VIN decode, repair estimates) — extend per integration."""

from __future__ import annotations

import json
import logging
import os

logger = logging.getLogger(__name__)


def handler(event: dict, context: object) -> dict:
    payload = json.loads(event["body"]) if isinstance(event.get("body"), str) else event
    claim_id = payload.get("claim_id", "unknown")
    enriched = {
        "claim_id": claim_id,
        "enrichment_version": os.environ.get("ENRICHMENT_VERSION", "0"),
        "notes": "Attach NHTSA vPIC / Mitchell integrations here",
    }
    return {"statusCode": 200, "body": json.dumps(enriched)}
