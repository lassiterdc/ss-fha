"""Analysis-method-level default constants for ss-fha.

These are the default values used by the SSFHA method that are NOT
case-study-specific. Every value here passes the test: "would a user
with a different study area and different data want the same value?"

Values that are case-study-specific (e.g., CRS EPSG, n_years_synthesized,
geospatial file paths, observed record length) are NOT included here.
Users must supply those explicitly in their YAML config files.

Default variable name mappings
-------------------------------
These control which xarray variable names are expected in input datasets.
Override them in your config YAML if your data uses different names.
"""

# --- Return period targets (years) ---
# Default return periods to evaluate flood hazard at.
# Override in your analysis YAML if your study requires different periods.
DEFAULT_RETURN_PERIODS: list[int] = [1, 2, 10, 100]

# --- Flood depth thresholds (meters) ---
# Used for flood impact categorization and mapping.
# Based on common flood hazard literature thresholds:
#   0.0025 m  — minimum detectable model output (essentially dry)
#   0.03 m    — nuisance flooding threshold
#   0.15 m    — ~6 inches; actionable flooding for pedestrians and vehicles
#   0.30 m    — ~1 foot; significant structural risk threshold
DEFAULT_DEPTH_THRESHOLDS_M: list[float] = [0.0025, 0.03, 0.15, 0.30]

# --- Bootstrap sampling ---
# Number of bootstrap samples for flood hazard uncertainty estimation.
# 500 provides stable 90% CI estimates while remaining computationally tractable.
DEFAULT_N_BOOTSTRAP_SAMPLES: int = 500

# --- Empirical plotting position ---
# Plotting position parameters (alpha, beta) for the generalized
# Hazen/Weibull family: F_i = (i - alpha) / (n + 1 - alpha - beta)
# Weibull (alpha=0, beta=0): F_i = i / (n + 1)
# This is an unbiased estimator for any distribution.
DEFAULT_PLOTTING_POSITION_METHOD: tuple[float, float] = (0.0, 0.0)

# --- Confidence interval alpha level ---
# Alpha for bootstrap confidence intervals (two-tailed).
# 0.10 → 90% CI, consistent with NOAA Atlas 14 IDF table reporting.
DEFAULT_BOOTSTRAP_CI_ALPHA: float = 0.10

# --- Variable name mappings ---
# Expected variable/coordinate names in input xarray datasets.
# These match the output conventions of TRITON-SWMM_toolkit.
DEFAULT_VAR_NAMES: dict[str, str] = {
    "flood_depth": "flood_depth",   # peak flood depth variable in TRITON zarr outputs
    "year": "year",                 # synthetic year coordinate
    "x": "x",                      # spatial x coordinate (CRS units)
    "y": "y",                      # spatial y coordinate (CRS units)
}
