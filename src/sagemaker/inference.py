"""SageMaker PyTorch serving entrypoint (JSON in → structured damage JSON out)."""

from __future__ import annotations

import json
import logging
import os

logger = logging.getLogger(__name__)


def model_fn(model_dir: str):  # pragma: no cover - executed on SageMaker
    model_id = os.environ.get("MODEL_ID", "google/paligemma-3b-pt-448")
    logger.info("Loading model configuration for %s", model_id)
    return {"model_id": model_id, "model_dir": model_dir}


def input_fn(request_body: str, content_type: str) -> dict:
    if content_type != "application/json":
        raise ValueError("Unsupported content type")
    return json.loads(request_body)


def _dev_analytical_record(input_data: dict, model: dict) -> dict:
    """Schema-valid dev stub using hints until fine-tuned weights are wired."""
    from claimlens.vlm_gate import route_vlm_output

    record = {
        "damage_class": input_data.get("damage_class_hint", "Unknown"),
        "severity": str(input_data.get("severity_hint", "MODERATE")).upper(),
        "confidence": float(input_data.get("confidence_hint", 0.5)),
        "damage_zones": list(input_data.get("damage_zones", [])),
        "repair_estimate_usd": input_data.get(
            "repair_estimate_usd", {"low": 0, "high": 0}
        ),
        "total_loss_risk": bool(input_data.get("total_loss_risk", False)),
        "etl_tags": list(input_data.get("etl_tags", [])),
        "pipeline_action": "FLAG_REVIEW",
        "model_id": model["model_id"],
        "dev_mode": True,
    }
    record["pipeline_action"] = route_vlm_output(record)
    return record


def predict_fn(input_data: dict, model: dict) -> dict:
    """Dev analytical stub: hint-based JSON validated and routed through vlm_gate."""
    return _dev_analytical_record(input_data, model)


def output_fn(prediction: dict, accept: str) -> tuple:
    if accept != "application/json":
        accept = "application/json"
    return json.dumps(prediction), accept
