"""
SageMaker training entrypoint for fine-tuning (Hugging Face Transformers).

Install `torch` and `transformers` in the training image; this script validates wiring.
"""

from __future__ import annotations

import argparse
import json
import logging
import os

logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model_id", default=os.environ.get("MODEL_ID", "google/paligemma-3b-pt-448"))
    parser.add_argument("--epochs", default="1")
    parser.add_argument("--learning_rate", default="2e-5")
    parser.add_argument("--train_manifest", default=os.environ.get("SM_CHANNEL_TRAIN", ""))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    logger.info(
        "train.py stub: model_id=%s epochs=%s lr=%s manifest=%s",
        args.model_id,
        args.epochs,
        args.learning_rate,
        args.train_manifest,
    )
    os.makedirs("/opt/ml/model", exist_ok=True)
    with open("/opt/ml/model/config.json", "w", encoding="utf-8") as handle:
        json.dump({"model_id": args.model_id}, handle)


if __name__ == "__main__":  # pragma: no cover
    logging.basicConfig(level=logging.INFO)
    main()
