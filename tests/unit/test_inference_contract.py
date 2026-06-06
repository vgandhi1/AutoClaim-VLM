"""Contract test: dev inference stub must pass vlm_gate."""

from claimlens.vlm_gate import route_vlm_output
from sagemaker.inference import predict_fn


def test_predict_fn_routes_through_gate():
    model = {"model_id": "dev-stub", "model_dir": "/tmp"}
    result = predict_fn(
        {
            "damage_class_hint": "Scratch",
            "severity_hint": "MINOR",
            "confidence_hint": 0.93,
            "damage_zones": ["door"],
        },
        model,
    )
    assert result["pipeline_action"] == route_vlm_output(result)
    assert result.get("dev_mode") is True
