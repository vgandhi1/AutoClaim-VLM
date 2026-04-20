from opensourceingest.sagemaker_manifest import build_sagemaker_manifest


def test_build_manifest_splits():
    records = [
        {
            "is_damaged": True,
            "damage_class": "Panel Scratch",
            "damage_severity": "MINOR",
            "processed_s3_key": "ds/a.jpg",
            "source_dataset": "kaggle_car_damage",
            "normalized_at": "2026-01-01T00:00:00+00:00",
        }
        for _ in range(10)
    ]
    train = build_sagemaker_manifest(records, split="train", train_pct=0.8, val_pct=0.1)
    val = build_sagemaker_manifest(records, split="validation", train_pct=0.8, val_pct=0.1)
    assert len(train) == 8
    assert len(val) == 1
