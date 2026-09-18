"""Specification of each morphometric measure CentileBrain can score.

A MeasureSpec ties the CentileBrain input template (column names and order) to the
FreeSurfer stats the values come from. Only the subcortical volume measure is defined
for now; cortical thickness and surface area will follow the same shape.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Region:
    column: str            # CentileBrain column name, e.g. "Lthal"
    hemi: str              # "L" or "R"
    structure: str         # short lower-case name, e.g. "thalamus"
    label: str             # display name, e.g. "Thalamus"
    aseg_names: tuple      # candidate StructName values in aseg.stats; first match wins


@dataclass(frozen=True)
class MeasureSpec:
    name: str              # CLI name, e.g. "subcortical"
    website_name: str      # as used in the website's output file names, e.g. "SubcorticalVolume"
    model_file: str        # upstream file name pattern with {sex} = male|female
    global_column: str     # the global covariate column in the template ("ICV")
    aseg_global_measure: str  # aseg.stats "# Measure" name the global covariate comes from
    regions: tuple

    @property
    def columns(self):
        """All template columns, in template order."""
        return ("SITE", "SubjectID", "Vendor", "FreeSurfer_Version", "age", "sex",
                self.global_column, *(r.column for r in self.regions))

    @property
    def region_columns(self):
        return tuple(r.column for r in self.regions)


def _pair(structure, label, aseg_stem):
    """Left/right Region pair for one subcortical structure."""
    return (
        Region(f"L{structure}", "L", label.lower(), label, tuple(f"Left-{s}" for s in aseg_stem)),
        Region(f"R{structure}", "R", label.lower(), label, tuple(f"Right-{s}" for s in aseg_stem)),
    )


SUBCORTICAL = MeasureSpec(
    name="subcortical",
    website_name="SubcorticalVolume",
    model_file="MFPmodels_subcorticalvolume_{sex}.rds",
    global_column="ICV",
    aseg_global_measure="EstimatedTotalIntraCranialVol",
    regions=(
        # Template order: thal, caud, put, pal, hippo, amyg, accumb; L before R.
        # "Thalamus-Proper" is the StructName used by FreeSurfer <= 7.1.
        *_pair("thal", "Thalamus", ("Thalamus", "Thalamus-Proper")),
        *_pair("caud", "Caudate", ("Caudate",)),
        *_pair("put", "Putamen", ("Putamen",)),
        *_pair("pal", "Pallidum", ("Pallidum",)),
        *_pair("hippo", "Hippocampus", ("Hippocampus",)),
        *_pair("amyg", "Amygdala", ("Amygdala",)),
        *_pair("accumb", "Accumbens", ("Accumbens-area",)),
    ),
)

MEASURE_SPECS = {SUBCORTICAL.name: SUBCORTICAL}
