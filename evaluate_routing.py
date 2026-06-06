"""
Dev analytical evaluation for VLM routing gate — no GPU or SageMaker required.

Runs schema validation + routing on a fixture corpus and prints a summary table
suitable for dev iteration before real VLM fine-tuning.

Usage:
    PYTHONPATH=src python evaluate_routing.py
    PYTHONPATH=src python evaluate_routing.py --fixtures tests/fixtures/routing_cases.json
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from claimlens.vlm_gate import route_vlm_output, validate_vlm_output

DEFAULT_FIXTURES = Path(__file__).parent / "tests" / "fixtures" / "routing_cases.json"


def _default_cases() -> list[dict]:
    return [
        {
            "name": "auto_approve_minor",
            "record": {
                "damage_class": "Scratch",
                "severity": "MINOR",
                "confidence": 0.93,
                "damage_zones": ["door"],
                "repair_estimate_usd": {"low": 100, "high": 300},
                "total_loss_risk": False,
                "etl_tags": [],
                "pipeline_action": "AUTO_APPROVE",
            },
            "expected_action": "AUTO_APPROVE",
        },
        {
            "name": "queue_moderate",
            "record": {
                "damage_class": "Dent",
                "severity": "MODERATE",
                "confidence": 0.80,
                "damage_zones": ["rear_bumper"],
                "repair_estimate_usd": {"low": 500, "high": 1500},
                "total_loss_risk": False,
                "etl_tags": [],
                "pipeline_action": "QUEUE_FOR_REPAIR",
            },
            "expected_action": "QUEUE_FOR_REPAIR",
        },
        {
            "name": "flag_review",
            "record": {
                "damage_class": "Crack",
                "severity": "MAJOR",
                "confidence": 0.65,
                "damage_zones": ["windshield"],
                "repair_estimate_usd": {"low": 800, "high": 2000},
                "total_loss_risk": False,
                "etl_tags": [],
                "pipeline_action": "FLAG_REVIEW",
            },
            "expected_action": "FLAG_REVIEW",
        },
        {
            "name": "total_loss_override",
            "record": {
                "damage_class": "Front Collision",
                "severity": "MINOR",
                "confidence": 0.95,
                "damage_zones": ["front_hood"],
                "repair_estimate_usd": {"low": 5000, "high": 12000},
                "total_loss_risk": True,
                "etl_tags": ["total_loss_candidate"],
                "pipeline_action": "ROUTE_TO_ADJUSTER",
            },
            "expected_action": "ROUTE_TO_ADJUSTER",
        },
        {
            "name": "low_confidence_adjuster",
            "record": {
                "damage_class": "Unknown",
                "severity": "MAJOR",
                "confidence": 0.45,
                "damage_zones": [],
                "repair_estimate_usd": {"low": 0, "high": 0},
                "total_loss_risk": False,
                "etl_tags": [],
                "pipeline_action": "ROUTE_TO_ADJUSTER",
            },
            "expected_action": "ROUTE_TO_ADJUSTER",
        },
    ]


def load_cases(path: Path) -> list[dict]:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return _default_cases()


def evaluate(cases: list[dict]) -> dict:
    schema_pass = 0
    routing_match = 0
    actions: Counter[str] = Counter()
    rows: list[dict] = []

    for case in cases:
        name = case.get("name", "unnamed")
        record = case["record"]
        expected = case.get("expected_action")
        row = {"name": name, "schema_ok": False, "action": None, "expected": expected, "match": False}
        try:
            validate_vlm_output(record)
            row["schema_ok"] = True
            schema_pass += 1
            action = route_vlm_output(record)
            row["action"] = action
            actions[action] += 1
            if expected is None or action == expected:
                row["match"] = True
                routing_match += 1
        except Exception as exc:
            row["error"] = str(exc)
        rows.append(row)

    total = len(cases)
    return {
        "total": total,
        "schema_pass_rate": round(schema_pass / total, 4) if total else 0.0,
        "routing_match_rate": round(routing_match / total, 4) if total else 0.0,
        "action_distribution": dict(actions),
        "rows": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Dev routing gate evaluation")
    parser.add_argument("--fixtures", type=Path, default=DEFAULT_FIXTURES)
    parser.add_argument("--out", type=Path, default=Path("models/routing_eval.json"))
    args = parser.parse_args()

    cases = load_cases(args.fixtures)
    report = evaluate(cases)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(f"\nRouting eval — {report['total']} cases\n")
    print(f"{'case':<28}{'schema':>8}{'action':>22}{'expected':>22}{'ok':>6}")
    for row in report["rows"]:
        ok = "✓" if row.get("match") else "✗"
        print(
            f"{row['name']:<28}"
            f"{str(row.get('schema_ok')):>8}"
            f"{str(row.get('action', '-')):>22}"
            f"{str(row.get('expected', '-')):>22}"
            f"{ok:>6}"
        )
    print(f"\nSchema pass rate:   {report['schema_pass_rate']:.0%}")
    print(f"Routing match rate: {report['routing_match_rate']:.0%}")
    print(f"Action distribution: {report['action_distribution']}")
    print(f"\nReport -> {args.out}\n")


if __name__ == "__main__":
    main()
