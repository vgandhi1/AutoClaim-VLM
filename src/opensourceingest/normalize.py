"""Canonical label normalization across open-source vehicle datasets."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

CANONICAL_DAMAGE_CLASSES = [
    "Front Collision",
    "Rear Impact",
    "Side Swipe",
    "Hood Dent",
    "Bumper Crack",
    "Glass Damage",
    "Panel Scratch",
    "Tire/Wheel Damage",
    "Underbody Damage",
    "Fire/Thermal",
    "Flood/Water Ingress",
    "Vandalism",
    "Unknown",
]

CANONICAL_SEVERITY = ["CRITICAL", "MAJOR", "MODERATE", "MINOR", "COSMETIC"]

CANONICAL_DAMAGE_ZONES = [
    "front_hood",
    "front_bumper",
    "rear_bumper",
    "trunk_lid",
    "door_panel_front_left",
    "door_panel_front_right",
    "door_panel_rear_left",
    "door_panel_rear_right",
    "front_quarter_panel_left",
    "front_quarter_panel_right",
    "rear_quarter_panel_left",
    "rear_quarter_panel_right",
    "windshield",
    "rear_glass",
    "side_glass_left",
    "side_glass_right",
    "headlight_left",
    "headlight_right",
    "taillight_left",
    "taillight_right",
    "wheel_front_left",
    "wheel_front_right",
    "wheel_rear_left",
    "wheel_rear_right",
    "rocker_panel",
    "roof",
    "underbody",
    "full_body",
]

CARDD_TO_CANONICAL: dict[str, dict[str, Any]] = {
    "Crack": {
        "damage_class": "Panel Scratch",
        "severity": "MODERATE",
        "confidence_adjustment": 0.0,
    },
    "Scratch": {
        "damage_class": "Panel Scratch",
        "severity": "COSMETIC",
        "confidence_adjustment": 0.0,
    },
    "Dent": {
        "damage_class": "Hood Dent",
        "severity": "MINOR",
        "confidence_adjustment": 0.0,
    },
    "Broken parts": {
        "damage_class": "Front Collision",
        "severity": "MAJOR",
        "confidence_adjustment": -0.10,
    },
    "Flattened": {
        "damage_class": "Tire/Wheel Damage",
        "severity": "MODERATE",
        "confidence_adjustment": 0.0,
    },
    "Lamp broken": {
        "damage_class": "Glass Damage",
        "severity": "MINOR",
        "confidence_adjustment": 0.0,
    },
}

KAGGLE_SEVERITY_TO_CANONICAL: dict[str, dict[str, str]] = {
    "01-minor": {"severity": "MINOR", "damage_class": "Panel Scratch"},
    "02-moderate": {"severity": "MODERATE", "damage_class": "Side Swipe"},
    "03-severe": {"severity": "MAJOR", "damage_class": "Front Collision"},
}

HF_VDD_TO_CANONICAL: dict[str, dict[str, str]] = {
    "damage": {"damage_class": "Unknown", "severity": "MODERATE"},
    "minor-dent": {"damage_class": "Hood Dent", "severity": "MINOR"},
    "major-dent": {"damage_class": "Hood Dent", "severity": "MAJOR"},
    "minor-scratch": {"damage_class": "Panel Scratch", "severity": "COSMETIC"},
    "major-scratch": {"damage_class": "Panel Scratch", "severity": "MODERATE"},
    "broken-windshield": {"damage_class": "Glass Damage", "severity": "MAJOR"},
    "flat-tire": {"damage_class": "Tire/Wheel Damage", "severity": "MODERATE"},
}

COMPCARS_PART_TO_ZONE: dict[int, list[str]] = {
    1: ["front_hood", "front_bumper"],
    2: ["rear_bumper", "trunk_lid"],
    3: ["door_panel_front_left", "door_panel_front_right"],
    4: ["full_body"],
    5: ["front_quarter_panel_left", "front_quarter_panel_right"],
    6: ["rear_quarter_panel_left", "rear_quarter_panel_right"],
}


def normalize_record(
    source_dataset: str,
    image_s3_key: str,
    raw_label: dict[str, Any],
    image_meta: dict[str, Any],
) -> dict[str, Any]:
    """Produce a canonical catalog record for downstream Glue / Redshift / training."""
    base: dict[str, Any] = {
        "image_id": str(uuid.uuid4()),
        "source_dataset": source_dataset,
        "source_label": raw_label,
        "image_s3_key": image_s3_key,
        "is_damaged": True,
        "damage_class": None,
        "damage_severity": None,
        "damage_zones": [],
        "has_segmentation_mask": False,
        "mask_s3_key": None,
        "make": image_meta.get("make"),
        "model": image_meta.get("model"),
        "year": image_meta.get("year"),
        "source_confidence": 1.0,
        "normalized_at": datetime.now(timezone.utc).isoformat(),
        "pipeline_stage": "OPEN_SOURCE_INGESTION",
    }

    if source_dataset == "compcars":
        part_id = int(raw_label.get("part_id", 4))
        base["is_damaged"] = False
        base["damage_class"] = None
        base["damage_severity"] = None
        base["damage_zones"] = COMPCARS_PART_TO_ZONE.get(part_id, ["full_body"])

    elif source_dataset == "cardd":
        category = str(raw_label.get("category_name", "Unknown"))
        mapping = CARDD_TO_CANONICAL.get(category, {})
        base["damage_class"] = mapping.get("damage_class", "Unknown")
        base["damage_severity"] = mapping.get("severity", "MODERATE")
        adj = float(mapping.get("confidence_adjustment", 0.0))
        base["source_confidence"] = round(1.0 + adj, 2)
        base["has_segmentation_mask"] = True
        base["mask_s3_key"] = raw_label.get("mask_s3_key")
        base["damage_zones"] = raw_label.get("inferred_zones") or ["full_body"]

    elif source_dataset == "kaggle_car_damage":
        folder = str(raw_label.get("severity_folder", "02-moderate"))
        mapping = KAGGLE_SEVERITY_TO_CANONICAL.get(folder, {})
        base["damage_class"] = mapping.get("damage_class", "Unknown")
        base["damage_severity"] = mapping.get("severity", "MODERATE")

    elif source_dataset == "kaggle_vehiface":
        folder = str(raw_label.get("severity_folder", "02-moderate"))
        mapping = KAGGLE_SEVERITY_TO_CANONICAL.get(folder, {})
        base["damage_class"] = mapping.get("damage_class", "Unknown")
        base["damage_severity"] = mapping.get("severity", "MODERATE")

    elif source_dataset == "stanford_cars":
        base["is_damaged"] = False
        base["damage_class"] = None
        base["damage_severity"] = None
        base["damage_zones"] = ["full_body"]

    elif source_dataset == "huggingface_vdd":
        label = str(raw_label.get("label", "damage"))
        mapping = HF_VDD_TO_CANONICAL.get(label, {})
        base["damage_class"] = mapping.get("damage_class", "Unknown")
        base["damage_severity"] = mapping.get("severity", "MODERATE")

    else:
        base["damage_class"] = "Unknown"
        base["damage_severity"] = "MODERATE"

    return base
