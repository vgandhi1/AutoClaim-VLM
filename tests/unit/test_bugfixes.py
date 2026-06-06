"""Regression tests for review bug-fixes (manifest, zones, dedup, schema)."""

import pytest

from glue.opensource_consolidation import PHASH_NEAR_DUP_THRESHOLD
from opensourceingest.cardd_downloader import _bbox_to_zones
from opensourceingest.image_quality import phash_hamming
from opensourceingest.sagemaker_manifest import build_sagemaker_manifest


def _records(source_dataset: str, n: int = 10):
    return [
        {
            "is_damaged": True,
            "damage_class": "Panel Scratch",
            "damage_severity": "MINOR",
            "processed_s3_key": f"ds/{i}.jpg",
            "source_dataset": source_dataset,
            "normalized_at": "2026-01-01T00:00:00+00:00",
        }
        for i in range(n)
    ]


def test_unknown_split_raises():
    with pytest.raises(ValueError):
        build_sagemaker_manifest(_records("cardd"), split="val")  # typo for "validation"


def test_human_annotated_only_for_cardd():
    import json

    cardd = json.loads(build_sagemaker_manifest(_records("cardd"), split="train")[0])
    kaggle = json.loads(
        build_sagemaker_manifest(_records("kaggle_car_damage"), split="train")[0]
    )
    assert cardd["vehicle-damage-label-metadata"]["human-annotated"] == "yes"
    assert kaggle["vehicle-damage-label-metadata"]["human-annotated"] == "no"


def test_bbox_to_zones_grid():
    assert _bbox_to_zones([0, 0, 10, 10], 100, 100) == ["top_left"]
    assert _bbox_to_zones([45, 45, 10, 10], 100, 100) == ["mid_center"]
    assert _bbox_to_zones([], 100, 100) == ["full_body"]


def test_near_dup_threshold_catches_small_diff():
    base = "1" * 64
    near = "0" + "1" * 63  # 1 bit different
    assert phash_hamming(base, near) <= PHASH_NEAR_DUP_THRESHOLD
