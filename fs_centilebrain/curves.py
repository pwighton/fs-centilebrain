"""Percentile curves over an age window around the subject, with ICV held at the subject's value."""

import logging
from pathlib import Path

import numpy as np
import pandas as pd

from .config import CURVE_STEP_YEARS, CURVE_WINDOW_YEARS, TRAINING_AGE_RANGE
from .measures import MeasureSpec
from .results import BAND_Z
from .scoring import SEX_NAME, score_cases

log = logging.getLogger("fs_centilebrain")


def age_grid(age: float, sex: str, window: float = CURVE_WINDOW_YEARS, step: float = CURVE_STEP_YEARS):
    """Ages age-window .. age+window in steps of `step`, always including `age` itself,
    clipped to the model's training range. Returns (ages, requested_window, used_window)."""
    lo, hi = TRAINING_AGE_RANGE[SEX_NAME[sex]]
    n = int(round(window / step))
    ages = age + step * np.arange(-n, n + 1)
    ages = np.round(ages, 6)
    ages = ages[(ages >= lo) & (ages <= hi)]
    requested = (round(age - window, 6), round(age + window, 6))
    used = (float(ages.min()), float(ages.max()))
    return ages, requested, used


def compute_curves(spec: MeasureSpec, sex: str, age: float, icv: float, model_dir: Path) -> tuple:
    """Returns (curves, settings): curves maps region column -> {age, p10, p50, p90} lists."""
    ages, requested, used = age_grid(age, sex)
    cases = pd.DataFrame({"age": ages, spec.global_column: icv})
    scored = score_cases(cases, spec, sex, model_dir)
    z_low, _, z_high = BAND_Z
    curves = {}
    for region in spec.region_columns:
        s = scored[scored.region == region].sort_values("row")
        pred = s.predicted.to_numpy()
        rmse = s.rmse.to_numpy()
        curves[region] = {
            "age": ages.tolist(),
            "p10": (pred + z_low * rmse).tolist(),
            "p50": pred.tolist(),
            "p90": (pred + z_high * rmse).tolist(),
        }
    settings = {
        "age_window_requested": list(requested),
        "age_window_used": list(used),
        "step_years": CURVE_STEP_YEARS,
        "icv_fixed_mm3": float(icv),
    }
    log.info("curves: %d ages from %.2f to %.2f (requested %.2f-%.2f), ICV fixed at %.0f mm3",
             len(ages), used[0], used[1], requested[0], requested[1], icv)
    return curves, settings
