from claimlens.vlm_gate import pipeline_action_from_vlm


def test_auto_approve_high_conf_minor():
    assert pipeline_action_from_vlm(0.91, "MINOR") == "AUTO_APPROVE"


def test_route_low_confidence():
    assert pipeline_action_from_vlm(0.2, "MAJOR") == "ROUTE_TO_ADJUSTER"
