import shutil
from pathlib import Path

import pytest

from fs_centilebrain.config import MODEL_DIR

REPO = Path(__file__).resolve().parents[1]
WEB_RESULTS = REPO / "reference" / "web-results"


def _r_and_models_available() -> bool:
    return shutil.which("Rscript") is not None and (MODEL_DIR / "MFPmodels_subcorticalvolume_male.rds").is_file()


requires_r = pytest.mark.skipif(not _r_and_models_available(),
                                reason="needs Rscript and the model files (run inside the container)")
