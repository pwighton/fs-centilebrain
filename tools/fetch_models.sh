#!/usr/bin/env bash
# Download the CentileBrain model files listed in models/checksums.sha256 from the
# pinned upstream commit and verify their checksums. Used by the Dockerfile; can
# also be run locally:  tools/fetch_models.sh /path/to/model/dir
set -euo pipefail

UPSTREAM_REPO="CentileBrain/centilebrain"
UPSTREAM_COMMIT="a532b6ff89ccd5fba3846b77b13a175fb9283c68"

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
checksums="${here}/../models/checksums.sha256"
dest="${1:?usage: fetch_models.sh DEST_DIR}"

mkdir -p "${dest}"
while read -r _sha name; do
    [[ -z "${name}" ]] && continue
    url="https://raw.githubusercontent.com/${UPSTREAM_REPO}/${UPSTREAM_COMMIT}/models/${name}"
    echo "fetching ${name}"
    curl -fsSL --retry 3 -o "${dest}/${name}" "${url}"
done < "${checksums}"

(cd "${dest}" && sha256sum -c "${checksums}")
echo "${UPSTREAM_COMMIT}" > "${dest}/UPSTREAM_COMMIT"
