#!/usr/bin/env bash
# Regenerate fs_centilebrain/data/offsets-subcortical.csv from the single-site website
# runs in reference/web-results/. Runs inside the container image (needs R + models).
#
#   tools/derive_offsets.sh [image]
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
IMAGE="${1:-pwighton/fs-centilebrain:latest}"

MALE=reference/web-results/single-site_male_2026-09-18-15-02-11
FEMALE=reference/web-results/single-site_female_2026-09-17-22-31-48
INPUT=reference/web-results/input_single-site_demo.xlsx

mkdir -p fs_centilebrain/data
docker run --rm --user "$(id -u):$(id -g)" -v "$PWD:/repo" -w /repo --entrypoint bash "${IMAGE}" -c "
  set -e
  python -c \"import pandas as pd; pd.read_excel('${INPUT}').to_csv('/tmp/demo.csv', index=False)\"
  Rscript tools/derive_offsets.R --model-dir \"\${FS_CENTILEBRAIN_MODEL_DIR}\" --input /tmp/demo.csv \
      --male ${MALE} --female ${FEMALE} --output fs_centilebrain/data/offsets-subcortical.csv
"
