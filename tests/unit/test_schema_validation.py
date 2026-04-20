import json
from pathlib import Path

import jsonschema


def test_vlm_output_schema_validates_example():
    root = Path(__file__).resolve().parents[2]
    schema_path = root / "src" / "schema" / "vlm_output_schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    example = {
        "damage_class": "Front Collision",
        "severity": "MAJOR",
        "confidence": 0.94,
        "damage_zones": ["front_hood", "front_bumper"],
        "repair_estimate_usd": {"low": 4000, "high": 9000},
        "total_loss_risk": False,
        "etl_tags": ["front_end"],
        "pipeline_action": "QUEUE_FOR_REPAIR",
    }
    jsonschema.validate(instance=example, schema=schema)
