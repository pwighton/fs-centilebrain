# fs-centilebrain

Local, containerised application of the [CentileBrain](https://centilebrain.org) normative models to a
single FreeSurfer subject. Produces percentile estimates, ICV-adjusted age curves and a PDF report,
without uploading anything to centilebrain.org.

Scope: subcortical volumes (14 regions from `aseg.stats`), sex-specific models. Cortical thickness and
surface area currently not implemented.

## Usage

```
docker run \
  --rm \
  --user $(id -u):$(id -g) \
  -v /path/to/subjects:/subjects \
  pwighton/fs-centilebrain:latest \
    --subject-dir /subjects \
    --subject bert \
    --male \
    --age 40 \
    --vendor Siemens
```

| Option | Description |
|---|---|
| `-sd`, `--subject-dir` | FreeSurfer `SUBJECTS_DIR` (as mounted in the container) |
| `-s`, `--subject` | FreeSurfer subject name |
| `-m`, `--male` / `-f`, `--female` | Sex (exactly one required) |
| `-a`, `--age` | Age at scan in years (float) |
| `-v`, `--vendor` | MR scanner vendor: `Siemens` (default), `GE`, `Philips`. Recorded in the input file; not used by the model |
| `--measure` | Morphometric measure to score; only `subcortical` for now |
| `--model-dir` | Directory holding the CentileBrain `.rds` files (default: the image's copy) |

Notes:

- `--user $(id -u):$(id -g)` makes the output files belong to you rather than root.
- The subject directory needs `stats/aseg.stats`; `scripts/build-stamp.txt` and `scripts/recon-all.done`
  are read if present (for the FreeSurfer version and a completeness check).
- Timestamps in the log and report use the container's time zone, `America/New_York` by default.
  Override with `-e TZ=<zone>` on the `docker run` line (e.g. `-e TZ=UTC`).
- Re-running on the same subject overwrites the previous `centilebrain/` outputs; the log describes the latest run only.

Exit codes: `0` success, `1` unexpected error (traceback in `centilebrain.log`), `2` usage or input error.

## Outputs

Everything is written to `<subject-dir>/<subject>/centilebrain/`:

```
input/centilebrain-input-subcortical.csv     values extracted from aseg.stats
input/centilebrain-input-subcortical.xlsx    same, in the format accepted by centilebrain.org
output/centilebrain-subcortical.json         all results (z, percentiles, asymmetry, curves, warnings, provenance)
output/prediction_SubcorticalVolume_<sex>.csv, zscore_SubcorticalVolume_<sex>.csv   website-format
output/plots/<structure>-<left|right>.png, output/plots/legend.png
output/normative-neuromorphometry-report--subject-<subject>.html              same content as the PDF
output/centilebrain.log
normative-neuromorphometry-report--subject-<subject>.pdf
```

The PDF is rendered from `output/centilebrain-subcortical.json` alone, so it can be regenerated
(for example after a layout change) without re-running the model:

```
docker run --rm --user $(id -u):$(id -g) -v /path/to/subjects:/subjects pwighton/fs-centilebrain:latest \
  report /subjects/bert/centilebrain/output/centilebrain-subcortical.json
```

### The report

- Header: subject, sex, age, intracranial volume (eTIV), vendor, FreeSurfer version, run date, model and tool versions.
- Warnings, if any (see below).
- One row per structure with left and right columns: measured volume, the model's 50th percentile, the 10th–90th
  percentile range, z-score and percentile. Values below the 10th or above the 90th percentile are highlighted
  and marked ↓ / ↑. The last column is the left–right asymmetry index.
- Plots of volume against age for each region, ±10 years around the subject's age, with the 10th, 50th and 90th
  percentile curves and the subject's measurement.

### Warnings

| Code | Meaning |
|---|---|
| `RECON_ALL_NOT_DONE` | `scripts/recon-all.done` is missing; recon-all may not have completed |
| `FS_VERSION_UNKNOWN` | no `x.y` version could be read from the build stamp (e.g. a dev build) |
| `FS_VERSION_NOT_IN_TRAINING` | the FreeSurfer version is not one the norms were built from (4.5, 5.1, 5.3, 7.1) |
| `AGE_OUT_OF_RANGE` | age outside the training range (about 3–90 years); results are an extrapolation |
| `CURVE_WINDOW_CLIPPED` | the ±10 year plot window was clipped to the training age range |
| `MODEL_CHECKSUM_MISMATCH` | the model file differs from the pinned upstream file |

## How to interpret the numbers

- **50th percentile / z / percentile.** The CentileBrain fractional-polynomial model predicts each regional volume
  from age and intracranial volume, separately for males and females, with a Gaussian residual of constant
  standard deviation. z is the subject's deviation from the prediction in units of that standard deviation and
  the percentile is 100·Φ(z). The JSON also carries an *empirical* percentile (the rank of the residual among the
  model's training residuals), which differs from the Gaussian one by a point or two in the tails.
- **10th–90th range.** The prediction ± 1.28 standard deviations. With 14 regions, a healthy person is expected
  to have about 2.8 regions outside this range by chance.
- **Curves.** Computed with intracranial volume held at the subject's value across the age window. That is a
  reasonable approximation in adulthood, less so in childhood.
- **Asymmetry index.** AI = 100·(L−R)/mean(L,R), i.e. 200·(L−R)/(L+R), in percent; positive when the left is
  larger. It is computed from the measured volumes only; CentileBrain provides no normative range for it.
- **Scanner and FreeSurfer version.** The normmative models were built from
  [data from many scanners and version of FreeSurfer (4.5–7.1)](https://docs.google.com/spreadsheets/d/1d-1bfKskhPSkfFnZXA68h9S7Lla6NRVU/edit?gid=1788754223#gid=1788754223). 
  No correction is performed for the subject's scanner or version; those effects
  are part of the normative spread. Output from newer FreeSurfer versions (7.2+, 8.x) has not been validated against these norms.
- **Measurement error** in the subject's own volumes (FreeSurfer test–retest variability) is not accounted for
  and is the dominant uncertainty for an individual percentile.

## Relationship to centilebrain.org

For a single subject the results are identical to what the website returns for a one-site upload (verified to
floating-point precision on the synthetic demo data and on a real subject; see `tests/test_scoring.py`). The
website's ComBat-GAM site harmonization only acts between sites *within* an upload, so it does nothing for a
single subject. `input/centilebrain-input-subcortical.xlsx` can be uploaded to the website as-is to cross-check.

The website's `centile_*.xlsx` file comes from a different, age-only model and is not reproduced here; the
curves in the report are derived from the same ICV-adjusted model as the z-scores.

## Building and testing

```
make build     # builds pwighton/fs-centilebrain:<version> (version from pyproject.toml) and :latest
make test      # builds, then runs the unit tests inside the image
make push      # builds, then pushes both tags
make version   # prints the version
```

The package can also be run outside the container (`pip install -e .[dev]`), in which case R must be
on the `PATH` and the model files must be fetched with `tools/fetch_models.sh DIR` and pointed to with
`--model-dir DIR` or `FS_CENTILEBRAIN_MODEL_DIR=DIR`. Tests that need R and the models skip when they are absent.

## Model files

The CentileBrain model files (`.rds`) are downloaded at image build time from a pinned commit of
https://github.com/CentileBrain/centilebrain and verified against `fs_centilebrain/data/model-checksums.sha256`
(again at run time, producing a warning on mismatch). They are not redistributed in this repository
(upstream publishes no license).

The models were trained on mean-centered data whose means are not published; the equivalent per-region
offsets in `fs_centilebrain/data/offsets-subcortical.csv` were derived from single-site website runs of the
demo data (`tools/derive_offsets.sh`, fixtures in `reference/web-results/`).

## Research use only

CentileBrain is provided by the ENIGMA Lifespan Working Group for research purposes. Nothing produced
by this tool is a diagnostic result.

## License

This repository is released under the BSD 2-clause License (see `LICENSE`). The license covers the code and
documentation here only.  The CentileBrain models remain subject to whatever terms their authors apply.
