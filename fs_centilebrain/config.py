"""Constants shared across the pipeline."""

import os
from pathlib import Path

VENDORS = ("Siemens", "GE", "Philips")
DEFAULT_VENDOR = "Siemens"

MEASURES = ("subcortical",)
DEFAULT_MEASURE = "subcortical"

# Upstream CentileBrain repository and the commit the model files are fetched from.
UPSTREAM_REPO = "https://github.com/CentileBrain/centilebrain"
UPSTREAM_COMMIT = "a532b6ff89ccd5fba3846b77b13a175fb9283c68"

# Where the Dockerfile puts the model files; overridable for local runs.
MODEL_DIR = Path(os.environ.get("FS_CENTILEBRAIN_MODEL_DIR", "/opt/centilebrain/models"))

# Name of the per-subject output folder inside the FreeSurfer subject directory.
OUTPUT_DIRNAME = "centilebrain"

# Percentile band drawn in the report.
BAND_PERCENTILES = (10, 50, 90)

# Age range of the training data per sex (min/max over the 14 subcortical GAMLSS objects'
# stored `xvar`; see docs/model-notes.md section 5).
TRAINING_AGE_RANGE = {"male": (3.42, 90.0), "female": (3.17, 90.06)}

# FreeSurfer versions represented in the training cohorts (major.minor).
TRAINING_FS_VERSIONS = ("4.5", "5.1", "5.3", "7.1")

# Age window around the subject's age for the curves, and the grid step.
CURVE_WINDOW_YEARS = 10.0
CURVE_STEP_YEARS = 0.25
