"""Build SageMaker-style augmented manifest lines from catalog records."""

from __future__ import annotations

import json
from typing import Any

# Only CarDD ships true human (COCO) annotations; the rest are programmatic
# labels derived from folder names / dataset fields / metadata.
_HUMAN_ANNOTATED_SOURCES = {"cardd"}


def build_sagemaker_manifest(
    catalog_records: list[dict[str, Any]],
    split: str = "train",
    train_pct: float = 0.80,
    val_pct: float = 0.10,
    processed_bucket: str = "vehicle-damage-opensource-processed",
) -> list[str]:
    labeled = [
        r
        for r in catalog_records
        if r.get("is_damaged") and r.get("damage_class") is not None
    ]
    n = len(labeled)
    if n == 0:
        return []

    t_end = int(n * train_pct)
    v_end = int(n * (train_pct + val_pct))
    splits = {
        "train": labeled[:t_end],
        "validation": labeled[t_end:v_end],
        "test": labeled[v_end:],
    }
    if split not in splits:
        raise ValueError(f"Unknown split {split!r}; must be one of {sorted(splits)}")
    subset = splits[split]

    lines: list[str] = []
    for record in subset:
        processed_key = record.get("processed_s3_key")
        if not processed_key:
            continue
        source_ref = f"s3://{processed_bucket}/{processed_key}"
        source_dataset = record.get("source_dataset", "unknown")
        human_annotated = "yes" if source_dataset in _HUMAN_ANNOTATED_SOURCES else "no"
        line = {
            "source-ref": source_ref,
            "vehicle-damage-label": {
                "damage_class": record["damage_class"],
                "severity": record["damage_severity"],
                "damage_zones": record.get("damage_zones", []),
                "is_damaged": record["is_damaged"],
                "source_confidence": record.get("source_confidence", 1.0),
            },
            "vehicle-damage-label-metadata": {
                "confidence": record.get("source_confidence", 1.0),
                "job-name": f"opensource-ingestion-{source_dataset}",
                "class-name": record["damage_class"],
                "human-annotated": human_annotated,
                "creation-date": record.get("normalized_at", ""),
                "type": "groundtruth/image-classification",
            },
        }
        lines.append(json.dumps(line))
    return lines
