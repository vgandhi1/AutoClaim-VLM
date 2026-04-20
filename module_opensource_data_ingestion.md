# Module: Open Source Vehicle Image Data Ingestion
## Addendum to: Vehicle Damage ETL & VLM Classification Pipeline

**Module Version:** 1.0  
**Scope:** Big data ingestion from CompCars, CarDD, Stanford Cars, Kaggle, HuggingFace  
**Target Volume:** 150,000–200,000 images into S3 landing zone  
**Purpose:** VLM fine-tuning corpus + damage classification ground truth

---

## Table of Contents

1. [Dataset Strategy & Selection](#1-dataset-strategy--selection)
2. [Dataset Profiles — Deep Dive](#2-dataset-profiles--deep-dive)
3. [Architecture — Open Source Ingestion Layer](#3-architecture--open-source-ingestion-layer)
4. [Label Schema Normalization](#4-label-schema-normalization)
5. [Ingestion Pipeline — Per Dataset](#5-ingestion-pipeline--per-dataset)
6. [AWS Glue Consolidation Job](#6-aws-glue-consolidation-job)
7. [Data Quality & Deduplication](#7-data-quality--deduplication)
8. [S3 Landing Zone Structure](#8-s3-landing-zone-structure)
9. [Fine-Tuning Data Pipeline for SageMaker](#9-fine-tuning-data-pipeline-for-sagemaker)
10. [Cost & Storage Estimates](#10-cost--storage-estimates)
11. [Legal & Licensing Guardrails](#11-legal--licensing-guardrails)
12. [Implementation Checklist](#12-implementation-checklist)

---

## 1. Dataset Strategy & Selection

### 1.1 Recommended Dataset Stack

The goal is maximum labeled image volume with complementary coverage across three needs: **vehicle body coverage** (undamaged baseline), **damage segmentation** (precise damage region masks), and **damage classification** (coarse labels matching your canonical schema).

```
┌──────────────────────────────────────────────────────────────────┐
│                    RECOMMENDED DATASET STACK                     │
│                                                                  │
│  PRIMARY (Volume + Vehicle Coverage)                             │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  CompCars  136,000 images  1,716 models  Part-annotated │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
│  DAMAGE GROUND TRUTH                                             │
│  ┌──────────────────────┐  ┌───────────────────────────────┐    │
│  │ CarDD  4,000 images  │  │ Kaggle Car Damage  ~1,500 img │    │
│  │ Segmentation masks   │  │ Binary + multi-class labels   │    │
│  └──────────────────────┘  └───────────────────────────────┘    │
│                                                                  │
│  SUPPLEMENTARY                                                   │
│  ┌──────────────────────┐  ┌───────────────────────────────┐    │
│  │ Stanford Cars 16,000 │  │ HuggingFace: vehicle-damage   │    │
│  │ Make/model metadata  │  │ Community datasets (filtered) │    │
│  └──────────────────────┘  └───────────────────────────────┘    │
│                                                                  │
│  SYNTHETIC (Generated via VLM + Stable Diffusion — optional)    │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  CompCars undamaged + damage overlay → labeled pairs    │    │
│  └─────────────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────────────┘

Total raw target: ~160,000 images
After QA filtering: ~120,000–140,000 usable images
```

### 1.2 Dataset Role Assignment

| Dataset | Primary Role | Why |
|---|---|---|
| **CompCars** | Undamaged baseline + vehicle body region understanding | 136K images, part-level annotations (front/rear/side/full), 1,716 models including EVs |
| **CarDD** | Damage segmentation ground truth | Pixel-level masks → precise damage zone extraction for VLM prompt enrichment |
| **Stanford Cars** | Make/model metadata enrichment | 196 car classes with fine-grained attributes — links to VIN decode for EV identification |
| **Kaggle: Car Damage Detection** | Quick damage class labels | Pre-labeled with categories mappable to your canonical schema |
| **HuggingFace** | Supplementary fill-in | Programmatic access, filterable by vehicle-related tags |

### 1.3 Why CompCars is the Anchor

**Scale advantage:** At 136K images, CompCars alone is 8× larger than all other automotive damage datasets combined. This volume is essential for:

- **Negative class training:** The VLM needs to understand "normal" vehicle appearance per body region before it can meaningfully assess "damaged" appearance
- **Transfer learning foundation:** Fine-tune PaliGemma first on CompCars vehicle understanding, then on damage labels — two-stage training outperforms single-stage on domain-specific tasks
- **Synthetic damage generation:** Overlay CarDD damage masks onto CompCars clean images to multiply labeled damage examples without additional human annotation cost

**Structural advantage:** CompCars annotates at the *part level* — hood, front bumper, rear bumper, door panels, wheels — which maps directly to your `damage_zones` JSON field. No other open dataset provides this.

**EV coverage:** CompCars includes Chinese EV manufacturers (BYD, NIO, SAIC) with significant representation — directly relevant to EV fleet damage assessment use cases.

---

## 2. Dataset Profiles — Deep Dive

### 2.1 CompCars (PRIMARY)

```
Full Name:    A Large-Scale Car Dataset for Fine-Grained Categorization and Verification
Institution:  CUHK (Chinese University of Hong Kong) + Tsinghua University
Release Year: 2015, updated 2016
Paper:        Sun et al., CVPR 2015
License:      Free for non-commercial research use (citation required)
```

**Volume Breakdown:**

| Subset | Images | Labels Available |
|---|---|---|
| Web images (scraped vehicle listings) | 136,726 | Make, model, year, part (front/rear/side/full/headlight/taillight/wheel) |
| Surveillance images (traffic cam) | 44,481 | Make, model, color |
| **Total** | **181,207** | |

**Directory Structure (after download):**

```
CompCars/
├── data/
│   ├── image/                     # web images organized by make/model/year
│   │   └── {make_id}/
│   │       └── {model_id}/
│   │           └── {year}/
│   │               └── {part_id}/
│   │                   └── *.jpg
│   ├── label/                     # bounding box annotations
│   │   └── {make_id}/{model_id}/{year}/{part_id}/*.txt
│   ├── misc/
│   │   ├── make_model_name.mat    # MATLAB file: make/model lookup
│   │   ├── car_type.mat           # body style (sedan/SUV/etc.)
│   │   └── attributes.txt         # 5 attributes per model
│   └── train_test_split/
│       ├── classification/
│       └── verification/
└── sv_data/                       # surveillance subset
```

**Part ID Mapping (critical for `damage_zones`):**

```python
COMPCARS_PART_MAP = {
    1: "front",           # → maps to damage_zone: "front_hood", "front_bumper"
    2: "rear",            # → "rear_bumper", "trunk"
    3: "side",            # → "door_panel", "rocker_panel"
    4: "full_body",       # → used for full vehicle assessment
    5: "front_side",      # → "front_quarter_panel"
    6: "rear_side",       # → "rear_quarter_panel"
}
```

**Access Method:**
```
Primary:  http://mmlab.ie.cuhk.edu.hk/datasets/comp_cars/
Mirror:   Google Drive link on dataset page (requires email registration)
Size:     ~32 GB (web subset), ~11 GB (surveillance)
Format:   JPEG images + MATLAB .mat files + .txt bounding boxes
```

**Parsing MATLAB `.mat` files (Python):**
```python
import scipy.io

def load_make_model_lookup(mat_path: str) -> dict:
    mat = scipy.io.loadmat(mat_path)
    makes = [str(m[0]) for m in mat["make_names"].flatten()]
    models = {}
    for i, model_list in enumerate(mat["model_names"].flatten()):
        for j, model in enumerate(model_list.flatten()):
            models[(i+1, j+1)] = {
                "make": makes[i],
                "model": str(model[0]) if model.size > 0 else "Unknown"
            }
    return models
```

---

### 2.2 CarDD (DAMAGE SEGMENTATION)

```
Full Name:    Car Damage Detection Dataset
Institution:  Beijing Institute of Technology
Release Year: 2022
Paper:        Wang et al., IEEE TIP 2023
License:      Academic use only
```

**Volume & Labels:**

| Split | Images | Annotations |
|---|---|---|
| Train | 3,800 | Instance segmentation masks (COCO format) |
| Val | 400 | Instance segmentation masks |
| Test | 200 | Instance segmentation masks |

**Damage Categories:**

```python
CARDD_CATEGORIES = {
    1: "Crack",           # → damage_class: "Panel Scratch" / "Glass Damage"
    2: "Scratch",         # → "Panel Scratch"
    3: "Dent",            # → "Hood Dent" / "Side Swipe"
    4: "Broken parts",    # → "Front Collision" / "Rear Impact"
    5: "Flattened",       # → "Tire/Wheel Damage"
    6: "Lamp broken",     # → "Glass Damage"
}
```

**Why CarDD is Essential:**
Pixel-level segmentation masks let you extract precise damage regions as crops, which become the input to VLM classification prompts. Instead of sending a full vehicle image to the VLM, you send a 640×640 crop of just the damaged zone — dramatically improving classification accuracy and reducing inference tokens.

**Access:**
```
GitHub:  https://github.com/CarDD-USTB/CarDD-SI
Format:  COCO JSON annotations + JPEG images
Size:    ~2.1 GB
```

---

### 2.3 Stanford Cars (METADATA ENRICHMENT)

```
Full Name:    Stanford Cars Dataset
Institution:  Stanford AI Lab
Release Year: 2013
License:      Free for research
```

**Volume:** 16,185 images across 196 classes (make + model + year combinations)

**Primary value for your pipeline:** Not the images themselves (16K is modest), but the **196 fine-grained class labels** with year ranges. This supplements CompCars with US-market vehicles heavily (whereas CompCars skews toward Chinese/Asian markets). Use it to improve VIN-to-make/model enrichment accuracy.

**Access:**
```
HuggingFace: datasets.load_dataset("Multimodal-Fatima/StanfordCars_train")
Kaggle:      kaggle datasets download jessicali9530/stanford-cars-dataset
Size:        ~1.9 GB
```

---

### 2.4 Kaggle: Car Damage Detection

```
Dataset:     Car Damage Severity Dataset
URL:         kaggle.com/datasets/anujms/car-damage-detector
License:     Open Database License (ODbL)
```

**Volume:** ~1,800 images

**Labels:**
```
01-minor   → severity: MINOR / COSMETIC
02-moderate → severity: MODERATE
03-severe  → severity: MAJOR / CRITICAL
```

**Second dataset:**
```
Dataset:  Vehicle Damage Detection
URL:      kaggle.com/datasets/hendrichscullen/vehiface-dataset
Images:   ~2,500
Labels:   damage location (front/rear/side) + severity
```

**Access via Kaggle API:**
```bash
pip install kaggle
export KAGGLE_USERNAME=your_username
export KAGGLE_KEY=your_api_key

kaggle datasets download anujms/car-damage-detector -p /tmp/kaggle/
kaggle datasets download hendrichscullen/vehiface-dataset -p /tmp/kaggle/
```

---

### 2.5 HuggingFace Datasets

**Relevant datasets available via `datasets` library:**

```python
from datasets import load_dataset

# Vehicle damage (community)
ds = load_dataset("keremberke/vehicle-damage-detection", split="train")
# ~3,900 images, YOLO-format bounding boxes, 6 damage classes

ds2 = load_dataset("Multimodal-Fatima/StanfordCars_train", split="train")
# Stanford Cars via HuggingFace hub

ds3 = load_dataset("imagenet-1k", split="train",
                   streaming=True)  # filter vehicle classes only (825+ vehicle synsets)
```

**HuggingFace filtering strategy for vehicle images from ImageNet:**
```python
VEHICLE_SYNSETS = [
    "n02958343",  # car, auto
    "n03100240",  # convertible
    "n03594945",  # jeep
    "n03670208",  # limousine
    "n03770679",  # minivan
    "n03777568",  # Model T (historic)
    "n04037443",  # racer
    "n04285008",  # sports car
    "n02974003",  # car wheel
    "n03459775",  # grille
    "n03786901",  # motor scooter (exclude)
]
# Filter streaming dataset by synset IDs to pull only car images
```

---

## 3. Architecture — Open Source Ingestion Layer

```
┌────────────────────────────────────────────────────────────────────────┐
│                   OPEN SOURCE DATA INGESTION LAYER                     │
│                                                                        │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────┐  │
│  │  CompCars    │  │   CarDD      │  │   Kaggle     │  │   HF     │  │
│  │  Downloader  │  │  Downloader  │  │  API Client  │  │  SDK     │  │
│  │  (EC2/Batch) │  │  (Lambda)    │  │  (Lambda)    │  │ (Lambda) │  │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └────┬─────┘  │
│         │                 │                  │               │        │
│         └─────────────────┴──────────────────┴───────────────┘        │
│                                    │                                   │
│                                    ▼                                   │
│              ┌─────────────────────────────────────┐                  │
│              │  S3: vehicle-damage-opensource-raw   │                  │
│              │  Partitioned by dataset source       │                  │
│              └─────────────────┬───────────────────┘                  │
│                                │                                       │
│                                ▼                                       │
│         ┌──────────────────────────────────────────────┐              │
│         │  AWS Glue: opensource-image-consolidation     │              │
│         │  ├── Image validation (blur, resolution)      │              │
│         │  ├── Perceptual hash deduplication            │              │
│         │  ├── Label schema normalization               │              │
│         │  ├── CompCars .mat file parsing               │              │
│         │  └── Canonical record construction            │              │
│         └──────────────────────┬───────────────────────┘              │
│                                │                                       │
│              ┌─────────────────┴─────────────────┐                    │
│              │                                   │                    │
│              ▼                                   ▼                    │
│  ┌───────────────────────┐        ┌──────────────────────────┐        │
│  │ S3: vehicle-damage-   │        │ Redshift:                │        │
│  │ processed/opensource/ │        │ opensource_image_catalog │        │
│  │ (normalized images)   │        │ (metadata + labels)      │        │
│  └───────────────────────┘        └──────────────────────────┘        │
│                                                │                       │
│                                                ▼                       │
│                          ┌─────────────────────────────────┐          │
│                          │  SageMaker Training Data Channel │          │
│                          │  (manifest file → fine-tuning)  │          │
│                          └─────────────────────────────────┘          │
└────────────────────────────────────────────────────────────────────────┘
```

### 3.1 New AWS Resources Required

| Resource | Spec | Purpose |
|---|---|---|
| **EC2 c5.2xlarge** (spot) | 8 vCPU, 16 GB RAM | CompCars download + extraction (32 GB archive) |
| **S3: `vehicle-damage-opensource-raw`** | Standard tier, versioning off | Raw dataset landing zone |
| **S3: `vehicle-damage-opensource-processed`** | Standard tier | Normalized images post-Glue |
| **Glue Job: `opensource-consolidation`** | G.2X, 4 workers | Parallel image processing across datasets |
| **Lambda: `dataset-downloaders`** | 3GB memory, 15 min timeout | CarDD / Kaggle / HuggingFace downloaders |
| **DynamoDB: `DatasetImageIndex`** | On-demand | Deduplication phash index across all datasets |
| **Step Functions** | Express workflow | Orchestrate multi-dataset ingestion order |
| **ECR: `compcars-downloader`** | Docker image | CompCars downloader with scipy/PIL/boto3 |

---

## 4. Label Schema Normalization

Every dataset uses its own taxonomy. The normalization layer maps all source labels to your canonical damage schema.

### 4.1 Master Normalization Map

```python
# ─── CANONICAL SCHEMA (target) ───────────────────────────────────────────────
CANONICAL_DAMAGE_CLASSES = [
    "Front Collision", "Rear Impact", "Side Swipe", "Hood Dent",
    "Bumper Crack", "Glass Damage", "Panel Scratch", "Tire/Wheel Damage",
    "Underbody Damage", "Fire/Thermal", "Flood/Water Ingress", "Vandalism", "Unknown"
]

CANONICAL_SEVERITY = ["CRITICAL", "MAJOR", "MODERATE", "MINOR", "COSMETIC"]

CANONICAL_DAMAGE_ZONES = [
    "front_hood", "front_bumper", "rear_bumper", "trunk_lid",
    "door_panel_front_left", "door_panel_front_right",
    "door_panel_rear_left", "door_panel_rear_right",
    "front_quarter_panel_left", "front_quarter_panel_right",
    "rear_quarter_panel_left", "rear_quarter_panel_right",
    "windshield", "rear_glass", "side_glass_left", "side_glass_right",
    "headlight_left", "headlight_right", "taillight_left", "taillight_right",
    "wheel_front_left", "wheel_front_right", "wheel_rear_left", "wheel_rear_right",
    "rocker_panel", "roof", "underbody", "full_body"
]

# ─── CarDD → Canonical ───────────────────────────────────────────────────────
CARDD_TO_CANONICAL = {
    "Crack": {
        "damage_class": "Panel Scratch",
        "severity": "MODERATE",
        "confidence_adjustment": 0.0,   # no adjustment needed
    },
    "Scratch": {
        "damage_class": "Panel Scratch",
        "severity": "COSMETIC",
        "confidence_adjustment": 0.0,
    },
    "Dent": {
        "damage_class": "Hood Dent",
        "severity": "MINOR",
        "confidence_adjustment": 0.0,
    },
    "Broken parts": {
        "damage_class": "Front Collision",  # most common for broken parts
        "severity": "MAJOR",
        "confidence_adjustment": -0.10,     # reduce confidence: ambiguous label
    },
    "Flattened": {
        "damage_class": "Tire/Wheel Damage",
        "severity": "MODERATE",
        "confidence_adjustment": 0.0,
    },
    "Lamp broken": {
        "damage_class": "Glass Damage",
        "severity": "MINOR",
        "confidence_adjustment": 0.0,
    },
}

# ─── Kaggle Car Damage → Canonical ───────────────────────────────────────────
KAGGLE_SEVERITY_TO_CANONICAL = {
    "01-minor":    {"severity": "MINOR",    "damage_class": "Panel Scratch"},
    "02-moderate": {"severity": "MODERATE", "damage_class": "Side Swipe"},
    "03-severe":   {"severity": "MAJOR",    "damage_class": "Front Collision"},
}

# ─── HuggingFace vehicle-damage-detection → Canonical ─────────────────────
HF_VDD_TO_CANONICAL = {
    "damage":           {"damage_class": "Unknown",       "severity": "MODERATE"},
    "minor-dent":       {"damage_class": "Hood Dent",     "severity": "MINOR"},
    "major-dent":       {"damage_class": "Hood Dent",     "severity": "MAJOR"},
    "minor-scratch":    {"damage_class": "Panel Scratch",  "severity": "COSMETIC"},
    "major-scratch":    {"damage_class": "Panel Scratch",  "severity": "MODERATE"},
    "broken-windshield":{"damage_class": "Glass Damage",  "severity": "MAJOR"},
    "flat-tire":        {"damage_class": "Tire/Wheel Damage","severity": "MODERATE"},
}

# ─── CompCars Part → Canonical Zone ──────────────────────────────────────────
COMPCARS_PART_TO_ZONE = {
    1: ["front_hood", "front_bumper"],
    2: ["rear_bumper", "trunk_lid"],
    3: ["door_panel_front_left", "door_panel_front_right"],
    4: ["full_body"],
    5: ["front_quarter_panel_left", "front_quarter_panel_right"],
    6: ["rear_quarter_panel_left", "rear_quarter_panel_right"],
}
# CompCars: no damage class (undamaged baseline) → damage_class = None, is_damaged = False
```

### 4.2 Normalization Function

```python
import uuid
from datetime import datetime

def normalize_record(
    source_dataset: str,
    image_s3_key: str,
    raw_label: dict,
    image_meta: dict,
) -> dict:
    """
    Produces a canonical record regardless of source dataset.
    All downstream processing (VLM, Redshift, DynamoDB) uses this schema.
    """
    base = {
        "image_id": str(uuid.uuid4()),
        "source_dataset": source_dataset,
        "source_label": raw_label,           # preserved for audit
        "image_s3_key": image_s3_key,
        "is_damaged": True,                  # overridden for CompCars
        "damage_class": None,
        "damage_severity": None,
        "damage_zones": [],
        "has_segmentation_mask": False,
        "mask_s3_key": None,
        "make": image_meta.get("make"),
        "model": image_meta.get("model"),
        "year": image_meta.get("year"),
        "source_confidence": 1.0,            # human-labeled = max confidence
        "normalized_at": datetime.utcnow().isoformat(),
        "pipeline_stage": "OPEN_SOURCE_INGESTION",
    }

    if source_dataset == "compcars":
        part_id = raw_label.get("part_id", 4)
        base["is_damaged"] = False
        base["damage_class"] = None
        base["damage_severity"] = None
        base["damage_zones"] = COMPCARS_PART_TO_ZONE.get(part_id, ["full_body"])

    elif source_dataset == "cardd":
        category = raw_label.get("category_name", "Unknown")
        mapping = CARDD_TO_CANONICAL.get(category, {})
        base["damage_class"] = mapping.get("damage_class", "Unknown")
        base["damage_severity"] = mapping.get("severity", "MODERATE")
        base["source_confidence"] = round(1.0 + mapping.get("confidence_adjustment", 0.0), 2)
        base["has_segmentation_mask"] = True
        base["mask_s3_key"] = raw_label.get("mask_s3_key")
        base["damage_zones"] = raw_label.get("inferred_zones", ["full_body"])

    elif source_dataset == "kaggle_car_damage":
        folder = raw_label.get("severity_folder", "02-moderate")
        mapping = KAGGLE_SEVERITY_TO_CANONICAL.get(folder, {})
        base["damage_class"] = mapping.get("damage_class", "Unknown")
        base["damage_severity"] = mapping.get("severity", "MODERATE")

    elif source_dataset == "stanford_cars":
        base["is_damaged"] = False
        base["damage_class"] = None

    elif source_dataset == "huggingface_vdd":
        label = raw_label.get("label", "damage")
        mapping = HF_VDD_TO_CANONICAL.get(label, {})
        base["damage_class"] = mapping.get("damage_class", "Unknown")
        base["damage_severity"] = mapping.get("severity", "MODERATE")

    return base
```

---

## 5. Ingestion Pipeline — Per Dataset

### 5.1 CompCars Downloader (EC2 Spot — Docker)

CompCars requires email registration for the Google Drive link. The downloader uses a pre-authenticated `gdown` token stored in Secrets Manager.

**Dockerfile:**
```dockerfile
FROM python:3.11-slim
RUN pip install gdown scipy pillow boto3 tqdm
COPY compcars_downloader.py /app/
WORKDIR /app
CMD ["python", "compcars_downloader.py"]
```

**`compcars_downloader.py`:**
```python
import gdown, tarfile, os, boto3, scipy.io, json
from pathlib import Path
from PIL import Image
from tqdm import tqdm

S3_RAW_BUCKET = "vehicle-damage-opensource-raw"
COMPCARS_GDRIVE_ID = "YOUR_GDRIVE_FILE_ID"  # from Secrets Manager
LOCAL_DOWNLOAD_PATH = "/tmp/compcars"
TARGET_S3_PREFIX = "compcars/web/"

def download_and_extract():
    os.makedirs(LOCAL_DOWNLOAD_PATH, exist_ok=True)
    print("Downloading CompCars archive (~32GB)...")
    gdown.download(
        f"https://drive.google.com/uc?id={COMPCARS_GDRIVE_ID}",
        f"{LOCAL_DOWNLOAD_PATH}/compcars.tar.gz", quiet=False
    )
    print("Extracting...")
    with tarfile.open(f"{LOCAL_DOWNLOAD_PATH}/compcars.tar.gz", "r:gz") as tar:
        tar.extractall(LOCAL_DOWNLOAD_PATH)

def load_labels(base_path: str) -> dict:
    """Parse MATLAB make/model lookup into Python dict."""
    mat = scipy.io.loadmat(f"{base_path}/data/misc/make_model_name.mat")
    makes = [str(m[0]) for m in mat["make_names"].flatten()]
    lookup = {}
    for make_id, model_arr in enumerate(mat["model_names"].flatten(), start=1):
        for model_id, model_name in enumerate(model_arr.flatten(), start=1):
            lookup[(make_id, model_id)] = {
                "make": makes[make_id - 1],
                "model": str(model_name[0]) if model_name.size > 0 else "Unknown"
            }
    return lookup

def upload_to_s3(local_root: str, label_lookup: dict):
    s3 = boto3.client("s3")
    image_root = Path(local_root) / "data" / "image"
    records = []

    for img_path in tqdm(list(image_root.rglob("*.jpg")), desc="Uploading to S3"):
        parts = img_path.relative_to(image_root).parts
        if len(parts) < 4:
            continue
        make_id, model_id, year, part_id = int(parts[0]), int(parts[1]), parts[2], int(parts[3])
        label_info = label_lookup.get((make_id, model_id), {"make": "Unknown", "model": "Unknown"})

        s3_key = f"{TARGET_S3_PREFIX}{make_id}/{model_id}/{year}/{part_id}/{img_path.name}"

        # Validate image before upload
        try:
            img = Image.open(img_path)
            w, h = img.size
            if w < 200 or h < 200:
                continue  # skip tiny images
        except Exception:
            continue

        s3.upload_file(str(img_path), S3_RAW_BUCKET, s3_key)
        records.append({
            "source_dataset": "compcars",
            "image_s3_key": s3_key,
            "make_id": make_id,
            "model_id": model_id,
            "year": year,
            "part_id": part_id,
            "make": label_info["make"],
            "model": label_info["model"],
        })

    # Write manifest to S3
    manifest_json = "\n".join(json.dumps(r) for r in records)
    s3.put_object(
        Bucket=S3_RAW_BUCKET,
        Key="compcars/manifest.jsonl",
        Body=manifest_json.encode("utf-8")
    )
    print(f"Uploaded {len(records)} CompCars images with manifest.")

if __name__ == "__main__":
    download_and_extract()
    labels = load_labels(LOCAL_DOWNLOAD_PATH)
    upload_to_s3(LOCAL_DOWNLOAD_PATH, labels)
```

**Run on EC2 Spot (c5.2xlarge, ~2 hours):**
```bash
aws ec2 run-instances \
  --image-id ami-0abcdef1234567890 \
  --instance-type c5.2xlarge \
  --instance-market-options '{"MarketType":"spot"}' \
  --iam-instance-profile Name=CompCarsDownloaderRole \
  --user-data file://compcars_ec2_startup.sh \
  --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=compcars-downloader}]'
```

---

### 5.2 CarDD Downloader (Lambda)

```python
import boto3, requests, zipfile, io, json, os

S3_RAW_BUCKET = "vehicle-damage-opensource-raw"
CARDD_GITHUB_RELEASE = "https://github.com/CarDD-USTB/CarDD-SI/archive/refs/heads/main.zip"

def handler(event, context):
    print("Downloading CarDD dataset...")
    resp = requests.get(CARDD_GITHUB_RELEASE, stream=True, timeout=600)
    resp.raise_for_status()

    s3 = boto3.client("s3")
    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
        for entry in zf.namelist():
            if entry.endswith(".jpg") or entry.endswith(".json"):
                key = f"cardd/{entry}"
                data = zf.read(entry)
                s3.put_object(Bucket=S3_RAW_BUCKET, Key=key, Body=data)
                print(f"Uploaded: {key}")

    # Parse COCO annotation JSON and write normalized manifest
    ann_key = "cardd/CarDD-SI-main/annotations/instances_train.json"
    ann_obj = s3.get_object(Bucket=S3_RAW_BUCKET, Key=ann_key)
    coco = json.loads(ann_obj["Body"].read())

    cat_map = {c["id"]: c["name"] for c in coco["categories"]}
    img_map = {img["id"]: img["file_name"] for img in coco["images"]}
    records = []

    for ann in coco["annotations"]:
        img_file = img_map[ann["image_id"]]
        cat_name = cat_map[ann["category_id"]]
        records.append({
            "source_dataset": "cardd",
            "image_s3_key": f"cardd/CarDD-SI-main/images/{img_file}",
            "category_name": cat_name,
            "bbox": ann["bbox"],
            "segmentation": ann.get("segmentation", []),
            "area": ann["area"],
            "annotation_id": ann["id"],
        })

    manifest = "\n".join(json.dumps(r) for r in records)
    s3.put_object(
        Bucket=S3_RAW_BUCKET,
        Key="cardd/manifest.jsonl",
        Body=manifest.encode("utf-8")
    )
    print(f"CarDD manifest written: {len(records)} annotations")
    return {"status": "ok", "records": len(records)}
```

---

### 5.3 Kaggle Downloader (Lambda)

```python
import boto3, subprocess, os, zipfile, json
from pathlib import Path

def handler(event, context):
    # Credentials from Secrets Manager
    sm = boto3.client("secretsmanager")
    secret = json.loads(sm.get_secret_value(SecretId="kaggle-api-credentials")["SecretString"])
    os.environ["KAGGLE_USERNAME"] = secret["username"]
    os.environ["KAGGLE_KEY"] = secret["key"]

    datasets = [
        {"slug": "anujms/car-damage-detector",     "name": "kaggle_car_damage"},
        {"slug": "hendrichscullen/vehiface-dataset","name": "kaggle_vehiface"},
    ]

    s3 = boto3.client("s3")
    for ds in datasets:
        download_path = f"/tmp/{ds['name']}"
        os.makedirs(download_path, exist_ok=True)

        # Download via Kaggle API
        subprocess.run([
            "kaggle", "datasets", "download",
            ds["slug"], "-p", download_path, "--unzip"
        ], check=True, timeout=600)

        # Upload images to S3 + build manifest
        records = []
        for img_path in Path(download_path).rglob("*.jpg"):
            folder = img_path.parent.name  # e.g. "01-minor", "02-moderate"
            s3_key = f"{ds['name']}/{folder}/{img_path.name}"
            s3.upload_file(str(img_path), "vehicle-damage-opensource-raw", s3_key)
            records.append({
                "source_dataset": ds["name"],
                "image_s3_key": s3_key,
                "severity_folder": folder,
            })

        manifest = "\n".join(json.dumps(r) for r in records)
        s3.put_object(
            Bucket="vehicle-damage-opensource-raw",
            Key=f"{ds['name']}/manifest.jsonl",
            Body=manifest.encode("utf-8")
        )
        print(f"{ds['name']}: {len(records)} images uploaded")
```

---

### 5.4 HuggingFace Downloader (Lambda)

```python
from datasets import load_dataset
import boto3, json
from PIL import Image
from io import BytesIO

HF_DATASETS = [
    {
        "name": "keremberke/vehicle-damage-detection",
        "split": "train",
        "s3_prefix": "huggingface_vdd",
        "image_col": "image",
        "label_col": "objects",
    },
]

def handler(event, context):
    s3 = boto3.client("s3")
    for ds_config in HF_DATASETS:
        print(f"Loading {ds_config['name']}...")
        dataset = load_dataset(ds_config["name"], split=ds_config["split"])
        records = []

        for i, example in enumerate(dataset):
            img: Image.Image = example[ds_config["image_col"]]
            buf = BytesIO()
            img.save(buf, format="JPEG", quality=90)
            buf.seek(0)

            s3_key = f"{ds_config['s3_prefix']}/{i:06d}.jpg"
            s3.put_object(
                Bucket="vehicle-damage-opensource-raw",
                Key=s3_key,
                Body=buf.read(),
                ContentType="image/jpeg"
            )

            # Extract label
            objs = example.get(ds_config["label_col"], {})
            label = objs.get("label", ["damage"])[0] if isinstance(objs, dict) else "damage"
            records.append({
                "source_dataset": ds_config["s3_prefix"],
                "image_s3_key": s3_key,
                "label": label,
                "index": i,
            })

        manifest = "\n".join(json.dumps(r) for r in records)
        s3.put_object(
            Bucket="vehicle-damage-opensource-raw",
            Key=f"{ds_config['s3_prefix']}/manifest.jsonl",
            Body=manifest.encode("utf-8")
        )
        print(f"{ds_config['name']}: {len(records)} images")
```

---

## 6. AWS Glue Consolidation Job

**Glue Job: `opensource-image-consolidation`**

This is the core normalization job. It reads all manifests from S3, applies label normalization, runs image quality checks, deduplicates via perceptual hash, and writes a unified catalog to Redshift and a normalized image set to the processed bucket.

```python
import sys, json, boto3, hashlib, base64
import numpy as np
from PIL import Image
from io import BytesIO
from awsglue.context import GlueContext
from awsglue.utils import getResolvedOptions
from pyspark.context import SparkContext
from pyspark.sql import Row

args = getResolvedOptions(sys.argv, ["JOB_NAME"])
sc = SparkContext()
glueContext = GlueContext(sc)
spark = glueContext.spark_session
s3 = boto3.client("s3")

RAW_BUCKET = "vehicle-damage-opensource-raw"
PROCESSED_BUCKET = "vehicle-damage-opensource-processed"
MANIFESTS = [
    "compcars/manifest.jsonl",
    "cardd/manifest.jsonl",
    "kaggle_car_damage/manifest.jsonl",
    "kaggle_vehiface/manifest.jsonl",
    "huggingface_vdd/manifest.jsonl",
]

# ── Step 1: Load all manifests ────────────────────────────────────────────────
all_records = []
for manifest_key in MANIFESTS:
    try:
        obj = s3.get_object(Bucket=RAW_BUCKET, Key=manifest_key)
        lines = obj["Body"].read().decode("utf-8").strip().split("\n")
        all_records.extend([json.loads(l) for l in lines if l.strip()])
        print(f"Loaded {len(lines)} records from {manifest_key}")
    except Exception as e:
        print(f"WARNING: Could not load {manifest_key}: {e}")

print(f"Total raw records: {len(all_records)}")

# ── Step 2: Distribute processing via Spark ───────────────────────────────────
records_rdd = sc.parallelize(all_records, numSlices=200)

def process_record(raw: dict) -> dict | None:
    """Per-image processing: validate, normalize, deduplicate, upload."""
    s3_client = boto3.client("s3")

    try:
        obj = s3_client.get_object(Bucket=RAW_BUCKET, Key=raw["image_s3_key"])
        img_bytes = obj["Body"].read()
        img = Image.open(BytesIO(img_bytes)).convert("RGB")
    except Exception as e:
        return {"status": "error", "reason": f"s3_read_failed: {e}", **raw}

    w, h = img.size

    # Quality checks
    img_array = np.array(img, dtype=np.float64)
    gray = np.mean(img_array, axis=2)
    from scipy.ndimage import convolve
    laplacian = np.array([[0,1,0],[1,-4,1],[0,1,0]])
    blur_score = float(np.var(convolve(gray, laplacian)))
    brightness = float(np.mean(img_array))

    if w < 224 or h < 224:
        return {"status": "rejected", "reason": "resolution_too_low", **raw}
    if blur_score < 50.0:
        return {"status": "rejected", "reason": "image_too_blurry", **raw}

    # Perceptual hash for deduplication
    small = img.resize((8, 8), Image.LANCZOS).convert("L")
    pixels = list(small.getdata())
    avg = sum(pixels) / len(pixels)
    phash = "".join("1" if p > avg else "0" for p in pixels)

    # Resize to 640×640 for model consistency
    img_resized = img.resize((640, 640), Image.LANCZOS)

    # Normalize labels
    canonical = normalize_record(
        source_dataset=raw["source_dataset"],
        image_s3_key=raw["image_s3_key"],
        raw_label=raw,
        image_meta={"make": raw.get("make"), "model": raw.get("model"), "year": raw.get("year")},
    )

    # Upload processed image
    processed_key = f"{raw['source_dataset']}/{canonical['image_id']}.jpg"
    buf = BytesIO()
    img_resized.save(buf, format="JPEG", quality=88)
    buf.seek(0)
    s3_client.put_object(Bucket=PROCESSED_BUCKET, Key=processed_key, Body=buf.read())

    return {
        **canonical,
        "status": "ok",
        "processed_s3_key": processed_key,
        "resolution_w": w,
        "resolution_h": h,
        "blur_score": blur_score,
        "brightness_mean": brightness,
        "phash_fingerprint": phash,
    }

processed_rdd = records_rdd.map(process_record).filter(lambda r: r is not None)

# ── Step 3: Deduplicate by phash ──────────────────────────────────────────────
ok_rdd = processed_rdd.filter(lambda r: r.get("status") == "ok")
deduped_rdd = ok_rdd.groupBy(lambda r: r["phash_fingerprint"]) \
                    .map(lambda g: sorted(g[1], key=lambda r: r["source_dataset"])[0])

print(f"After deduplication: {deduped_rdd.count()} unique images")

# ── Step 4: Write to Redshift via S3 staging ──────────────────────────────────
df = spark.createDataFrame(deduped_rdd.map(lambda r: Row(**{
    k: v for k, v in r.items()
    if k in ["image_id", "source_dataset", "image_s3_key", "processed_s3_key",
             "is_damaged", "damage_class", "damage_severity", "damage_zones",
             "has_segmentation_mask", "mask_s3_key", "make", "model", "year",
             "source_confidence", "normalized_at", "resolution_w", "resolution_h",
             "blur_score", "brightness_mean", "phash_fingerprint", "status"]
})))

df.write.format("jdbc") \
  .option("url", "jdbc:redshift://cluster.ACCOUNT.us-east-1.redshift.amazonaws.com:5439/vehicle_damage") \
  .option("dbtable", "vehicle_damage.opensource_image_catalog") \
  .option("user", "etl_writer") \
  .option("password", "{{REDSHIFT_PASSWORD}}") \
  .option("driver", "com.amazon.redshift.jdbc42.Driver") \
  .mode("append") \
  .save()

print("Consolidation complete.")
```

---

## 7. Data Quality & Deduplication

### 7.1 Cross-Dataset Deduplication Strategy

Images scraped from vehicle listing sites (CompCars) and insurance datasets (Kaggle) overlap significantly. Three-layer deduplication:

```
Layer 1: S3 key deduplication    → exact filename match (fast, cheap)
Layer 2: MD5 hash deduplication  → exact byte-for-byte duplicate
Layer 3: Perceptual hash (pHash) → visually similar (same photo, different JPEG quality)
         Hamming distance < 8    → considered duplicate
```

**pHash Hamming distance check (Spark UDF):**
```python
from pyspark.sql.functions import udf
from pyspark.sql.types import BooleanType

@udf(returnType=BooleanType())
def is_duplicate_phash(hash1: str, hash2: str, threshold: int = 8) -> bool:
    if hash1 is None or hash2 is None or len(hash1) != len(hash2):
        return False
    hamming = sum(c1 != c2 for c1, c2 in zip(hash1, hash2))
    return hamming < threshold
```

**Deduplication priority (which copy to keep):**
```
1. CarDD (has segmentation mask → highest value)
2. Kaggle (has damage label)
3. HuggingFace (has damage label)
4. CompCars (no damage label, but highest resolution)
5. Stanford Cars (metadata only)
```

### 7.2 Great Expectations Suite — Open Source Catalog

```python
OPENSOURCE_EXPECTATIONS = [
    # Image IDs unique
    expect_column_values_to_be_unique("image_id"),
    # pHash unique (deduplication check)
    expect_column_values_to_be_unique("phash_fingerprint"),
    # Source dataset coverage — all 5 datasets must be present
    expect_column_distinct_values_to_contain_set(
        "source_dataset",
        ["compcars", "cardd", "kaggle_car_damage", "huggingface_vdd", "stanford_cars"]
    ),
    # Damage class valid when is_damaged = True
    expect_column_values_to_be_in_set(
        "damage_class", CANONICAL_DAMAGE_CLASSES + [None]
    ),
    # Resolution after preprocessing
    expect_column_values_to_equal("resolution_w", 640),
    expect_column_values_to_equal("resolution_h", 640),
    # Blur score above minimum
    expect_column_values_to_be_between("blur_score", min_value=50.0),
    # At least 60% images should be is_damaged = True (CompCars pulls this down)
    expect_column_mean_to_be_between("is_damaged", min_value=0.35, max_value=1.0),
]
```

### 7.3 Dataset Balance Monitoring

After consolidation, check class balance before using for fine-tuning:

```sql
SELECT
    source_dataset,
    is_damaged,
    damage_class,
    damage_severity,
    COUNT(*) AS image_count,
    ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (PARTITION BY source_dataset), 1) AS pct_of_source
FROM vehicle_damage.opensource_image_catalog
WHERE status = 'ok'
GROUP BY 1, 2, 3, 4
ORDER BY 1, 5 DESC;
```

**Target class distribution for fine-tuning (after SMOTE/oversampling):**
```
CRITICAL:  5–8%    (rare but critical to detect)
MAJOR:     12–15%
MODERATE:  20–25%
MINOR:     25–30%
COSMETIC:  20–25%
Undamaged: 15–20%  (negative class from CompCars)
```

---

## 8. S3 Landing Zone Structure

```
s3://vehicle-damage-opensource-raw/
├── compcars/
│   ├── manifest.jsonl                    ← 136K records
│   └── web/
│       └── {make_id}/{model_id}/{year}/{part_id}/
│           └── *.jpg
│
├── cardd/
│   ├── manifest.jsonl                    ← 4,400 annotation records
│   └── CarDD-SI-main/
│       ├── images/
│       │   ├── train/  *.jpg
│       │   └── val/    *.jpg
│       └── annotations/
│           ├── instances_train.json      ← COCO format
│           └── instances_val.json
│
├── kaggle_car_damage/
│   ├── manifest.jsonl
│   └── data/
│       ├── 01-minor/     *.jpg
│       ├── 02-moderate/  *.jpg
│       └── 03-severe/    *.jpg
│
├── kaggle_vehiface/
│   ├── manifest.jsonl
│   └── *.jpg
│
└── huggingface_vdd/
    ├── manifest.jsonl
    └── *.jpg   (000000.jpg … 003899.jpg)

s3://vehicle-damage-opensource-processed/
├── compcars/      {image_id}.jpg  (640×640, normalized)
├── cardd/         {image_id}.jpg
├── kaggle_car_damage/ {image_id}.jpg
├── kaggle_vehiface/   {image_id}.jpg
└── huggingface_vdd/   {image_id}.jpg

s3://vehicle-damage-opensource-processed/
└── fine_tuning/
    ├── train/
    │   ├── manifest.json       ← SageMaker training channel format
    │   └── images/  {image_id}.jpg
    ├── validation/
    │   ├── manifest.json
    │   └── images/
    └── test/
        ├── manifest.json
        └── images/
```

---

## 9. Fine-Tuning Data Pipeline for SageMaker

### 9.1 Training Manifest Format (SageMaker Ground Truth Compatible)

```python
def build_sagemaker_manifest(
    catalog_records: list,
    split: str = "train",
    train_pct: float = 0.80,
    val_pct: float = 0.10,
) -> list:
    """
    Produces SageMaker-compatible augmented manifest format.
    Only includes records with confirmed damage labels (is_damaged = True).
    """
    labeled = [r for r in catalog_records if r["is_damaged"] and r["damage_class"] is not None]
    n = len(labeled)
    splits = {
        "train": labeled[:int(n * train_pct)],
        "validation": labeled[int(n * train_pct):int(n * (train_pct + val_pct))],
        "test": labeled[int(n * (train_pct + val_pct)):],
    }

    manifest_lines = []
    for record in splits[split]:
        line = {
            "source-ref": f"s3://vehicle-damage-opensource-processed/{record['processed_s3_key']}",
            "vehicle-damage-label": {
                "damage_class": record["damage_class"],
                "severity": record["damage_severity"],
                "damage_zones": record["damage_zones"],
                "is_damaged": record["is_damaged"],
                "source_confidence": record["source_confidence"],
            },
            "vehicle-damage-label-metadata": {
                "confidence": record["source_confidence"],
                "job-name": f"opensource-ingestion-{record['source_dataset']}",
                "class-name": record["damage_class"],
                "human-annotated": "yes" if record["source_dataset"] != "synthetic" else "no",
                "creation-date": record["normalized_at"],
                "type": "groundtruth/image-classification",
            }
        }
        manifest_lines.append(json.dumps(line))

    return manifest_lines
```

### 9.2 SageMaker Training Job Configuration

```python
import boto3

sm = boto3.client("sagemaker")

training_job = sm.create_training_job(
    TrainingJobName="paligemma-vehicle-damage-ft-v1",
    AlgorithmSpecification={
        "TrainingImage": "763104351884.dkr.ecr.us-east-1.amazonaws.com/huggingface-pytorch-training:2.1.0-transformers4.37.0-gpu-py310-cu121-ubuntu22.04",
        "TrainingInputMode": "FastFile",
    },
    RoleArn="arn:aws:iam::ACCOUNT:role/SageMakerTrainingRole",
    InputDataConfig=[
        {
            "ChannelName": "train",
            "DataSource": {
                "S3DataSource": {
                    "S3DataType": "AugmentedManifestFile",
                    "S3Uri": "s3://vehicle-damage-opensource-processed/fine_tuning/train/manifest.json",
                    "S3DataDistributionType": "FullyReplicated",
                    "AttributeNames": ["source-ref", "vehicle-damage-label"],
                }
            },
        },
        {
            "ChannelName": "validation",
            "DataSource": {
                "S3DataSource": {
                    "S3DataType": "AugmentedManifestFile",
                    "S3Uri": "s3://vehicle-damage-opensource-processed/fine_tuning/validation/manifest.json",
                    "S3DataDistributionType": "FullyReplicated",
                    "AttributeNames": ["source-ref", "vehicle-damage-label"],
                }
            },
        },
    ],
    OutputDataConfig={
        "S3OutputPath": "s3://vehicle-damage-opensource-processed/model-artifacts/"
    },
    ResourceConfig={
        "InstanceType": "ml.g5.2xlarge",    # A10G GPU — sufficient for PaliGemma 3B
        "InstanceCount": 1,
        "VolumeSizeInGB": 100,
    },
    StoppingCondition={"MaxRuntimeInSeconds": 86400},
    HyperParameters={
        "model_id": "google/paligemma-3b-pt-448",
        "epochs": "10",
        "learning_rate": "2e-5",
        "batch_size": "8",
        "warmup_ratio": "0.1",
        "lr_scheduler_type": "cosine",
        "output_format": "json",           # force structured JSON output
        "task": "VQA",
    },
)

print(f"Training job started: {training_job['TrainingJobArn']}")
```

### 9.3 Data Augmentation Strategy

To increase effective dataset size beyond 120K images, apply these augmentations in the Glue job:

```python
from PIL import Image, ImageEnhance
import random

def augment_image(img: Image.Image, seed: int = 42) -> list:
    """Returns 4 augmented variants of each labeled damage image."""
    random.seed(seed)
    augmented = []

    # 1. Horizontal flip (mirror — damage can be on either side)
    augmented.append(img.transpose(Image.FLIP_LEFT_RIGHT))

    # 2. Brightness variation (lighting conditions at capture)
    enhancer = ImageEnhance.Brightness(img)
    augmented.append(enhancer.enhance(random.uniform(0.7, 1.3)))

    # 3. Rotation ±15° (camera angle variation)
    angle = random.uniform(-15, 15)
    augmented.append(img.rotate(angle, fillcolor=(128, 128, 128)))

    # 4. JPEG quality variation (simulates phone camera compression)
    buf = BytesIO()
    img.save(buf, format="JPEG", quality=random.randint(60, 95))
    buf.seek(0)
    augmented.append(Image.open(buf))

    return augmented

# Apply only to damage-labeled images (not undamaged CompCars baseline)
# Expected output: ~120K original + ~480K augmented = ~600K training images
```

---

## 10. Cost & Storage Estimates

### 10.1 One-Time Ingestion Cost

| Component | Operation | Estimated Cost |
|---|---|---|
| EC2 c5.2xlarge Spot (CompCars, ~2hr) | Download + extract + upload 32GB | ~$0.80 |
| S3 PUT requests (136K CompCars + 10K others) | ~150K PUT requests | ~$0.75 |
| Lambda invocations (CarDD + Kaggle + HF) | ~50K invocations, 3GB × 15min | ~$2.50 |
| Glue G.2X × 4 workers × 3 hours | Consolidation + normalization | ~$8.80 |
| S3 data transfer (uploads) | ~50GB total across all datasets | ~$4.50 |
| **Total one-time ingestion** | | **~$17.35** |

### 10.2 Storage Costs (Monthly)

| Bucket | Estimated Size | Monthly Cost |
|---|---|---|
| `vehicle-damage-opensource-raw` | ~45 GB | ~$1.04 |
| `vehicle-damage-opensource-processed` | ~38 GB (640×640 JPEG) | ~$0.87 |
| Redshift catalog table (150K rows) | < 1 GB | Negligible |
| **Total storage** | **~83 GB** | **~$1.91/month** |

### 10.3 SageMaker Fine-Tuning Cost

| Run | Instance | Duration | Cost |
|---|---|---|---|
| Initial fine-tune (10 epochs, 120K images) | ml.g5.2xlarge | ~6 hours | ~$14.50 |
| Re-run after augmentation (600K images) | ml.g5.2xlarge | ~24 hours | ~$58.00 |
| Monthly calibration re-tune | ml.g5.2xlarge | ~4 hours | ~$9.70 |

---

## 11. Legal & Licensing Guardrails

| Dataset | License | Commercial Use | Required Citation | PII Risk |
|---|---|---|---|---|
| **CompCars** | Academic non-commercial | ❌ No | Sun et al., CVPR 2015 | Low (vehicle images only) |
| **CarDD** | Academic non-commercial | ❌ No | Wang et al., IEEE TIP 2023 | Low |
| **Stanford Cars** | Research only | ❌ No | Krause et al., ICCV 2013 | Low |
| **Kaggle Car Damage** | ODbL (open database) | ✅ Yes (with attribution) | Dataset page credit | Low |
| **HuggingFace VDD** | Apache 2.0 | ✅ Yes | Model card credit | Low |

**Risk mitigation for non-commercial datasets in a portfolio/production context:**

1. **Isolation:** Keep open source data in a separate S3 bucket and Redshift schema (`opensource_`) from operational claims data (`vehicle_damage.vehicle_damage_claims`). VLM fine-tuned on open source data; production inference runs on real claims.
2. **Fine-tuning only:** Open source images are used exclusively as training data — they are never surfaced in production API responses or customer-facing systems.
3. **No redistribution:** Processed/augmented images stay within your AWS account. Do not publish derived datasets.
4. **Portfolio disclosure:** When documenting this project, note "VLM fine-tuned on CompCars (CUHK), CarDD (BIT), and Kaggle open datasets under academic license for research and portfolio purposes."

---

## 12. Implementation Checklist

### Week 1 — Setup & CompCars

- [ ] Register for CompCars dataset at mmlab.ie.cuhk.edu.hk
- [ ] Store Google Drive credentials in Secrets Manager
- [ ] Create S3 buckets: `vehicle-damage-opensource-raw` and `-processed`
- [ ] Build and push CompCars downloader Docker image to ECR
- [ ] Launch EC2 Spot instance — download + upload CompCars (~2 hours)
- [ ] Verify: `compcars/manifest.jsonl` exists with ~136K records
- [ ] Write MATLAB `.mat` parser — verify make/model lookup for 10 sample records

### Week 2 — CarDD + Kaggle + HuggingFace

- [ ] Deploy Lambda `cardd-downloader` — test with 100-record subset
- [ ] Store Kaggle API credentials in Secrets Manager
- [ ] Deploy Lambda `kaggle-downloader` — verify both datasets land in S3
- [ ] Deploy Lambda `huggingface-downloader` — test HF dataset loading
- [ ] Verify all 5 dataset manifests present in S3

### Week 3 — Glue Consolidation

- [ ] Write and unit test `normalize_record()` function for all 5 dataset types
- [ ] Deploy Glue job `opensource-image-consolidation`
- [ ] Run on 1,000-record subset first — verify output quality
- [ ] Full run: ~150K images, ~3 hours on G.2X × 4 workers
- [ ] Run Great Expectations suite against `opensource_image_catalog` table
- [ ] Verify deduplication: check duplicate phash count = 0

### Week 4 — Fine-Tuning Data Prep

- [ ] Run `build_sagemaker_manifest()` — produce train/val/test split manifests
- [ ] Check class balance SQL query — apply SMOTE/oversampling if CRITICAL < 3%
- [ ] Run augmentation job — produce augmented set (~600K images)
- [ ] Launch SageMaker training job `paligemma-vehicle-damage-ft-v1`
- [ ] Monitor training: TensorBoard via SageMaker Experiments
- [ ] Evaluate on test set: target accuracy > 80% per damage class
- [ ] Register model in SageMaker Model Registry
- [ ] A/B test: route 10% of real claims to fine-tuned endpoint vs base PaliGemma

### Ongoing

- [ ] Monthly: re-run calibration against adjuster ground truth (ECE < 0.05)
- [ ] Quarterly: check for new open source vehicle damage datasets
- [ ] Monitor: `vlm_avg_confidence` metric — trigger fine-tuning re-run if drops below 0.78

---

*Module maintained alongside: `vehicle_damage_etl_project_plan.md`*  
*Dataset access and licensing should be re-verified before any commercial deployment.*
