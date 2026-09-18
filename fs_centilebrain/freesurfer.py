"""Reading what we need from a FreeSurfer subject directory."""

import re
from dataclasses import dataclass, field
from pathlib import Path


class FreeSurferError(Exception):
    pass


@dataclass
class AsegStats:
    path: Path
    measures: dict = field(default_factory=dict)   # "# Measure" rows, keyed by both long and short name
    volumes: dict = field(default_factory=dict)    # StructName -> Volume_mm3

    def volume(self, *candidates: str) -> float:
        """Volume of the first StructName among ``candidates`` present in the file."""
        for name in candidates:
            if name in self.volumes:
                return self.volumes[name]
        raise FreeSurferError(f"none of {candidates} found in {self.path}")

    def measure(self, name: str) -> float:
        try:
            return self.measures[name]
        except KeyError:
            raise FreeSurferError(f"measure {name!r} not found in {self.path}") from None


def parse_aseg_stats(path: Path) -> AsegStats:
    """Parse an aseg.stats file (mri_segstats output).

    Header lines look like
        # Measure EstimatedTotalIntraCranialVol, eTIV, Estimated Total Intracranial Volume, 1518348.145089, mm^3
        # ColHeaders  Index SegId NVoxels Volume_mm3 StructName normMean ...
    followed by one whitespace-separated row per structure.
    """
    stats = AsegStats(path=path)
    columns = None
    with open(path) as fh:
        for line in fh:
            if line.startswith("# Measure "):
                parts = [p.strip() for p in line[len("# Measure "):].split(",")]
                if len(parts) < 5:
                    raise FreeSurferError(f"malformed Measure line in {path}: {line.strip()}")
                value = float(parts[3])
                stats.measures[parts[0]] = value
                stats.measures[parts[1]] = value
            elif line.startswith("# ColHeaders"):
                columns = line.split()[2:]
            elif line.startswith("#") or not line.strip():
                continue
            else:
                if columns is None:
                    raise FreeSurferError(f"table row before ColHeaders in {path}")
                row = dict(zip(columns, line.split()))
                stats.volumes[row["StructName"]] = float(row["Volume_mm3"])
    if not stats.volumes:
        raise FreeSurferError(f"no segmentation rows found in {path}")
    return stats


_VERSION_RE = re.compile(r"(?<![\d.])(\d+\.\d+(?:\.\d+)?)(?![\d.])")


def read_build_stamp(subject_path: Path):
    """Raw contents of scripts/build-stamp.txt, or None if absent."""
    stamp = subject_path / "scripts" / "build-stamp.txt"
    if not stamp.is_file():
        return None
    return stamp.read_text().strip()


def freesurfer_version(build_stamp) -> str:
    """Version string for the input file: "7.3.2" from
    "freesurfer-linux-ubuntu20_x86_64-7.3.2-20220804-6354275"; the raw stamp when no
    x.y[.z] is present (dev builds); "unknown" when there is no stamp at all.
    """
    if not build_stamp:
        return "unknown"
    match = _VERSION_RE.search(build_stamp)
    return match.group(1) if match else build_stamp


def recon_all_done(subject_path: Path) -> bool:
    return (subject_path / "scripts" / "recon-all.done").is_file()
