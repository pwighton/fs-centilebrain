FROM rocker/r-ver:4.3.3

ENV DEBIAN_FRONTEND=noninteractive

# python3 for the pipeline, curl for fetching the models, pango/fonts for WeasyPrint (PDF report)
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    python3-venv \
    curl \
    ca-certificates \
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    libharfbuzz0b \
    fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

# CentileBrain model files: fetched from the pinned upstream commit, checksum-verified.
ENV FS_CENTILEBRAIN_MODEL_DIR=/opt/centilebrain/models
COPY models/checksums.sha256 /opt/centilebrain/src/models/checksums.sha256
COPY tools/fetch_models.sh /opt/centilebrain/src/tools/fetch_models.sh
RUN bash /opt/centilebrain/src/tools/fetch_models.sh "${FS_CENTILEBRAIN_MODEL_DIR}"

# Python package
ENV VIRTUAL_ENV=/opt/venv
RUN python3 -m venv "${VIRTUAL_ENV}"
ENV PATH="${VIRTUAL_ENV}/bin:${PATH}"
COPY pyproject.toml README.md LICENSE /opt/centilebrain/src/
COPY fs_centilebrain /opt/centilebrain/src/fs_centilebrain
RUN pip install --no-cache-dir /opt/centilebrain/src[dev]

# Tests are copied so the suite can be run inside the image:  docker run --entrypoint pytest fs-centilebrain
COPY tests /opt/centilebrain/src/tests
COPY reference /opt/centilebrain/src/reference
WORKDIR /opt/centilebrain/src

# Provenance: set by the Makefile at build time
ARG GIT_SHA=unknown
ARG IMAGE_TAG=pwighton/fs-centilebrain:dev
ENV FS_CENTILEBRAIN_GIT_SHA=${GIT_SHA} \
    FS_CENTILEBRAIN_IMAGE=${IMAGE_TAG}

ENTRYPOINT ["fs-centilebrain"]
CMD ["--help"]
