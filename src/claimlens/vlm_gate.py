"""Confidence-based routing rules for ClaimLens."""

from __future__ import annotations


def pipeline_action_from_vlm(confidence: float, severity: str) -> str:
    sev = severity.upper()
    if confidence >= 0.90 and sev in {"MINOR", "COSMETIC"}:
        return "AUTO_APPROVE"
    if confidence >= 0.75 and sev in {"MODERATE", "MAJOR"}:
        return "QUEUE_FOR_REPAIR"
    if confidence >= 0.60:
        return "FLAG_REVIEW"
    return "ROUTE_TO_ADJUSTER"
