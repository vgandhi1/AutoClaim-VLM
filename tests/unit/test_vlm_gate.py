
from claimlens.vlm_gate import pipeline_action_from_vlm, route_vlm_output


def test_auto_approve_high_conf_minor():
    assert pipeline_action_from_vlm(0.91, "MINOR") == "AUTO_APPROVE"


def test_route_low_confidence():
    assert pipeline_action_from_vlm(0.2, "MAJOR") == "ROUTE_TO_ADJUSTER"


def test_queue_for_repair_moderate():
    assert pipeline_action_from_vlm(0.80, "MODERATE") == "QUEUE_FOR_REPAIR"


def test_flag_review_boundary():
    assert pipeline_action_from_vlm(0.65, "MAJOR") == "FLAG_REVIEW"


def test_total_loss_risk_overrides_confidence():
    assert pipeline_action_from_vlm(0.95, "MINOR", total_loss_risk=True) == "ROUTE_TO_ADJUSTER"


def test_route_vlm_output_enforces_schema_and_routing():
    record = {
        "damage_class": "Front Collision",
        "severity": "MINOR",
        "confidence": 0.92,
        "damage_zones": ["front_bumper"],
        "repair_estimate_usd": {"low": 100, "high": 200},
        "total_loss_risk": False,
        "etl_tags": ["front_end"],
        "pipeline_action": "AUTO_APPROVE",
    }
    assert route_vlm_output(record) == "AUTO_APPROVE"
