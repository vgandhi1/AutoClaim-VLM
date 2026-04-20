from opensourceingest.normalize import normalize_record


def test_compcars_baseline():
    rec = normalize_record(
        "compcars",
        "compcars/web/1/2/2012/4/x.jpg",
        {"part_id": 1},
        {"make": "BYD", "model": "Seal", "year": "2024"},
    )
    assert rec["is_damaged"] is False
    assert rec["damage_class"] is None
    assert "front_hood" in rec["damage_zones"]


def test_cardd_mapping():
    rec = normalize_record(
        "cardd",
        "cardd/CarDD-SI-main/images/train/1.jpg",
        {"category_name": "Scratch", "mask_s3_key": "m1", "inferred_zones": ["front_bumper"]},
        {},
    )
    assert rec["is_damaged"] is True
    assert rec["damage_class"] == "Panel Scratch"
    assert rec["damage_severity"] == "COSMETIC"
    assert rec["has_segmentation_mask"] is True


def test_kaggle_severity():
    rec = normalize_record(
        "kaggle_car_damage",
        "kaggle_car_damage/03-severe/a.jpg",
        {"severity_folder": "03-severe"},
        {},
    )
    assert rec["damage_severity"] == "MAJOR"


def test_hf_vdd():
    rec = normalize_record(
        "huggingface_vdd",
        "huggingface_vdd/000001.jpg",
        {"label": "flat-tire"},
        {},
    )
    assert rec["damage_class"] == "Tire/Wheel Damage"
