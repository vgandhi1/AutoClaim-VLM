#!/usr/bin/env bash
set -euo pipefail

echo "Bootstrapping CompCars downloader container"

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker is required on this instance" >&2
  exit 1
fi

: "${ECR_IMAGE:?Set ECR_IMAGE to the compcars downloader image URI}"

docker pull "${ECR_IMAGE}"
docker run --rm \
  -e COMPCARS_GDRIVE_FILE_ID \
  -e CLAIMLENS_RAW_BUCKET \
  -e COMPCARS_LOCAL_ROOT=/tmp/compcars \
  "${ECR_IMAGE}"
