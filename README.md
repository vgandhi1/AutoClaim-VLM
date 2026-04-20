# ClaimLens README — Patch Notes
# Apply these exact changes to README.md

# ── FIX 1: Replace YOUR_USERNAME in two places ────────────────────────────────

# Line ~155 (Getting Started Step 1):
# BEFORE:
git clone https://github.com/YOUR_USERNAME/claimlens.git
# AFTER:
git clone https://github.com/vgandhi1/claimlens.git

# Line ~280 (Citation block):
# BEFORE:
  url     = {https://github.com/YOUR_USERNAME/claimlens},
# AFTER:
  url     = {https://github.com/vgandhi1/claimlens},


# ── FIX 2: Correct the macOS-only date command ────────────────────────────────

# BEFORE:
  --start-time $(date -u -v-5M +%FT%TZ) \
# AFTER:
  --start-time $(date -u -d '5 minutes ago' +%FT%TZ) \   # Linux
  # macOS: replace with $(date -u -v-5M +%FT%TZ)


# ── FIX 3: Add missing files to repo structure tree ──────────────────────────

# Under src/sagemaker/, add:
│   ├── sagemaker/
│   │   ├── inference.py
│   │   ├── train.py
│   │   ├── deploy_endpoint.py          # ← ADD THIS
│   │   └── prompt_templates/
│   │       ├── v1.0.txt
│   │       └── v2.3.txt

# Under src/opensourceingest/, add:
│   ├── opensourceingest/
│   │   ├── compcars_downloader.py
│   │   ├── compcars_ec2_startup.sh     # ← ADD THIS
│   │   ├── cardd_downloader.py
│   │   ├── kaggle_downloader.py
│   │   ├── huggingface_downloader.py
│   │   └── normalize.py

# Under infrastructure/, add:
├── infrastructure/
│   ├── main.tf
│   ├── variables.tf
│   ├── variables.tf.example            # ← ADD THIS
│   ├── outputs.tf
│   └── modules/

# At root level, add:
├── README.md
├── LICENSE
├── requirements.txt                    # ← ADD THIS (top-level project deps)
├── requirements-test.txt               # ← ADD THIS (test deps)
├── pyproject.toml                      # ← OPTIONAL but recommended
├── CONTRIBUTING.md                     # ← OPTIONAL but recommended


# ── FIX 4: Correct Roadmap checkboxes to honest state ────────────────────────

# Only mark [x] if the code is actually committed. Suggested honest state:
# (adjust based on what's actually in your repo)

- [x] Core ETL pipeline structure (ingest → preprocess → load)
- [x] VLM classification engine with confidence gating
- [x] Open source corpus ingestion downloaders (CompCars + CarDD + Kaggle + HuggingFace)
- [x] Label normalization across 5 dataset schemas
- [x] Redshift schema DDL + DynamoDB index definition
- [ ] Terraform IaC modules (in progress)
- [ ] CloudWatch alarms + X-Ray tracing (in progress)
- [ ] PaliGemma 3B fine-tuning on consolidated corpus
- [ ] SAP ERP integration (ROUTE_TO_ADJUSTER action)
- [ ] QuickSight dashboard (claims volume, severity trends, VLM accuracy)
- [ ] Jetson Nano edge pre-filter (CLIP ViT-B/32 TensorRT INT8)
- [ ] Confidence calibration monthly job (ECE tracking)
- [ ] Synthetic damage data generation (CompCars + CarDD mask overlay)
- [ ] VIN-level fleet damage aggregation queries


# ── ADD: Core Library Files table (place after Repository Structure header) ──

## Core Library

| Module | Description |
|---|---|
| `src/claimlens/processing.py` | Image preprocessing: Laplacian blur scoring, perceptual hashing, CLAHE contrast enhancement, 640×640 resize |
| `src/claimlens/vlm_gate.py` | VLM output validation (JSON Schema draft-07), confidence-based routing logic, total loss override |
| `src/schema/vlm_output_schema.json` | Canonical JSON Schema contract — validated before every downstream write |
| `src/schema/redshift_ddl.sql` | Full DDL for all 4 Redshift tables with DISTKEY/SORTKEY definitions |


# ── ADD: Local Development section (place before Contributing) ───────────────

## Local Development

Run core pipeline modules locally without AWS credentials:

```bash
# Create virtual environment
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Test image preprocessing on a local file
python -m claimlens.processing \
  --image tests/fixtures/test_car_damage.jpg \
  --output /tmp/claimlens_out/

# Validate VLM output schema against a sample response
python -m claimlens.vlm_gate \
  --input tests/fixtures/sample_vlm_responses/front_collision.json

# Run full unit test suite (no AWS required)
pytest tests/unit/ -v --cov=src/claimlens --cov-report=term-missing
```

> AWS credentials are only required for integration tests and infrastructure deployment.
> All unit tests run fully offline against local fixtures.
