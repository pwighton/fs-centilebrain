# fs-centilebrain

Local, containerised application of the [CentileBrain](https://centilebrain.org) normative models to a
single FreeSurfer subject. Produces percentile estimates, ICV-adjusted age curves and a PDF report,
without uploading anything to centilebrain.org.

Status: under construction. See `20260917-fs-centilebrains-implementation.md` for the plan and the
current step, and `docs/model-notes.md` for what we know about the models.

Scope of the first implementation: subcortical volumes (14 regions from `aseg.stats`), sex-specific
models. Cortical thickness and surface area are planned.

## Intended usage

```
docker run \
  --rm \
  --user $(id -u):$(id -g) \
  -v /path/to/subjects:/subjects \
  fs-centilebrain \
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
| `-a`, `--age` | Age in years (float) |
| `-v`, `--vendor` | MR scanner vendor: `Siemens` (default), `GE`, `Philips` |

Results are written to `<subject-dir>/<subject>/centilebrain/`:

```
input/centilebrain-input-subcortical.csv     values extracted from aseg.stats
input/centilebrain-input-subcortical.xlsx    same, in the format accepted by centilebrain.org
output/centilebrain-subcortical.json         all results (z, percentiles, curves, provenance)
output/prediction_SubcorticalVolume_<sex>.csv, zscore_SubcorticalVolume_<sex>.csv   website-format
output/plots/<region>.png
output/centilebrain.log
centilebrain-report.pdf
```

## Model files

The CentileBrain model files (`.rds`) are downloaded at image build time from a pinned commit of
https://github.com/CentileBrain/centilebrain and verified by checksum. They are not redistributed in
this repository (upstream publishes no license).

## Research use only

CentileBrain is provided by the ENIGMA Lifespan Working Group for research purposes. Nothing produced
by this tool is a diagnostic result.
