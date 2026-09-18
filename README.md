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
| `-a`, `--age` | Age in years (float) |
| `-v`, `--vendor` | MR scanner vendor: `Siemens` (default), `GE`, `Philips` |

Results are written to `<subject-dir>/<subject>/centilebrain/`:

```
input/centilebrain-input-subcortical.csv     values extracted from aseg.stats
input/centilebrain-input-subcortical.xlsx    same, in the format accepted by centilebrain.org
output/centilebrain-subcortical.json         all results (z, percentiles, curves, provenance)
output/prediction_SubcorticalVolume_<sex>.csv, zscore_SubcorticalVolume_<sex>.csv   website-format
output/plots/<structure>-<left|right>.png, output/plots/legend.png
output/centilebrain-report.html               same content as the PDF
output/centilebrain.log
centilebrain-report.pdf
```

The PDF is rendered from `output/centilebrain-subcortical.json` alone, so it can be regenerated
(for example after a layout change) without re-running the model:

```
docker run --rm --user $(id -u):$(id -g) -v /path/to/subjects:/subjects pwighton/fs-centilebrain:latest \
  report /subjects/bert/centilebrain/output/centilebrain-subcortical.json
```

## Building and testing

```
make build     # builds pwighton/fs-centilebrain:<version> (version from pyproject.toml) and :latest
make test      # builds, then runs the unit tests inside the image
make push      # builds, then pushes both tags
make version   # prints the version
```

The package can also be run outside the container (`pip install -e .[dev]`), in which case R must be
on the `PATH` and the model files must be fetched with `tools/fetch_models.sh DIR` and pointed to with
`--model-dir DIR` or `FS_CENTILEBRAIN_MODEL_DIR=DIR`.

## Model files

The CentileBrain model files (`.rds`) are downloaded at image build time from a pinned commit of
https://github.com/CentileBrain/centilebrain and verified by checksum. They are not redistributed in
this repository (upstream publishes no license).

## Research use only

CentileBrain is provided by the ENIGMA Lifespan Working Group for research purposes. Nothing produced
by this tool is a diagnostic result.

## License

This repository is released under the BSD 2-clause License (see `LICENSE`). The license covers the code and
documentation here only.  The CentileBrain models remain subject to whatever terms their authors apply.
