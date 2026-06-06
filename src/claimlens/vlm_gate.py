"""Confidence-based routing rules and runtime schema enforcement for ClaimLens."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

import jsonschema

_SCHEMA_PATH = Path(__file__).resolve().parents[1] / "schema" / "vlm_output_schema.json"


@lru_cache(maxsize=1)
def _load_schema() -> dict[str, Any]:
    return json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))


def validate_vlm_output(data: dict[str, Any]) -> None:
    """Validate a VLM output record against the canonical schema.

    Raises jsonschema.ValidationError if the record does not conform. Call this
    before routing or writing any VLM output to S3/Redshift/DynamoDB.
    """
    jsonschema.validate(instance=data, schema=_load_schema())


def pipeline_action_from_vlm(
    confidence: float,
    severity: str,
    *,
    total_loss_risk: bool = False,
) -> str:
    if total_loss_risk:
        return "ROUTE_TO_ADJUSTER"
    sev = severity.upper()
    if confidence >= 0.90 and sev in {"MINOR", "COSMETIC"}:
        return "AUTO_APPROVE"
    if confidence >= 0.75 and sev in {"MODERATE", "MAJOR"}:
        return "QUEUE_FOR_REPAIR"
    if confidence >= 0.60:
        return "FLAG_REVIEW"
    return "ROUTE_TO_ADJUSTER"


def route_vlm_output(data: dict[str, Any]) -> str:
    """Enforce schema, then return the pipeline action for a VLM output record.

    This is the single gate that downstream writers should call: it guarantees a
    record is schema-valid before it is acted on or persisted.
    """
    validate_vlm_output(data)
    return pipeline_action_from_vlm(
        data["confidence"],
        data["severity"],
        total_loss_risk=bool(data.get("total_loss_risk", False)),
    )


def _main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Validate and route a VLM output JSON file.")
    parser.add_argument("--input", required=True, help="Path to a VLM output JSON file.")
    args = parser.parse_args()

    data = json.loads(Path(args.input).read_text(encoding="utf-8"))
    try:
        action = route_vlm_output(data)
    except jsonschema.ValidationError as exc:
        print(f"INVALID: {exc.message}")
        return 1
    print(f"VALID -> pipeline_action: {action}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
