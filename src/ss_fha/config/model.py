"""Pydantic v2 configuration models for ss-fha.

Two top-level models:
  - SystemConfig  — fixed geographic context for a study area (system.yaml)
  - SSFHAConfig   — discriminated union on fha_approach (analysis_*.yaml)
      SsfhaConfig  (fha_approach="ssfha")
      BdsConfig    (fha_approach="bds")

Analysis vs. comparative analysis
----------------------------------
An "analysis" is the primary config for a study area. It owns event return
period calculations and may reference comparative analyses via alt_fha_analyses.

A "comparative analysis" is a lighter config (is_comparative_analysis=True) that
represents an alternative FHA approach. It must not contain event_statistics,
alt_fha_analyses, or toggle_mcds=True.

Existence checks for Path fields are deferred to validation.py (01E).
This module validates structure, types, and toggle-dependency consistency only.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, Field, model_validator

from ss_fha.constants import WEATHER_EVENT_INDEX_YEAR_ALIASES
from ss_fha.exceptions import ConfigurationError

# ---------------------------------------------------------------------------
# SystemConfig sub-models
# ---------------------------------------------------------------------------


class GeospatialConfig(BaseModel):
    watershed: Path
    roads: Path | None = None
    sidewalks: Path | None = None
    buildings: Path | None = None
    parcels: Path | None = None
    fema_flood_raster: Path | None = None
    fema_flood_raster_return_period_yr: int | None = None


class SystemConfig(BaseModel):
    study_area_id: str
    crs_epsg: int
    geospatial: GeospatialConfig

    @model_validator(mode="after")
    def validate_fema_fields_paired(self) -> SystemConfig:
        raster = self.geospatial.fema_flood_raster
        return_pd = self.geospatial.fema_flood_raster_return_period_yr
        if (raster is None) != (return_pd is None):
            missing = "fema_flood_raster_return_period_yr" if raster is not None else "fema_flood_raster"
            provided = "fema_flood_raster" if raster is not None else "fema_flood_raster_return_period_yr"
            raise ConfigurationError(
                field=missing,
                message=(
                    f"'{provided}' is set but '{missing}' is missing. "
                    "Both must be provided together, or both must be null."
                ),
            )
        return self


# ---------------------------------------------------------------------------
# Shared analysis sub-models
# ---------------------------------------------------------------------------


class TritonOutputsConfig(BaseModel):
    combined: Path
    observed: Path | None = None
    surge_only: Path | None = None
    rain_only: Path | None = None
    triton_only_combined: Path | None = None


class EventDataConfig(BaseModel):
    sim_event_summaries: Path
    sim_event_timeseries: Path | None = None
    sim_event_iloc_mapping: Path | None = None
    obs_event_summaries: Path | None = None
    obs_event_timeseries: Path | None = None
    obs_event_iloc_mapping: Path | None = None


class PPCCTConfig(BaseModel):
    n_years_observed: int


class UncertaintyConfig(BaseModel):
    """Bootstrap uncertainty estimation configuration.

    Required when ``toggle_uncertainty=True`` on the parent ``SsfhaConfig``.

    Attributes
    ----------
    n_bootstrap_samples:
        Number of bootstrap resamples to generate. 500 provides stable 90% CI
        estimates (see DEFAULT_N_BOOTSTRAP_SAMPLES in config/defaults.py).
    bootstrap_base_seed:
        Base integer seed for the bootstrap RNG. Each sample ``i`` uses
        ``np.random.default_rng(bootstrap_base_seed + i)``, ensuring every
        sample is independently reproducible. Record this value alongside your
        outputs for full run reproducibility.
    bootstrap_quantiles:
        Quantiles to compute across bootstrap samples for the combined CI
        output. Specified as fractions in (0, 1). Typical choice: [0.05, 0.50,
        0.95] for a 90% confidence interval with median. Must contain at least
        one value.
    """

    n_bootstrap_samples: int
    bootstrap_base_seed: int
    bootstrap_quantiles: list[float]


class FloodRiskConfig(BaseModel):
    """Flood risk assessment configuration (fields added in chunk 01E / Phase 3F)."""

    pass


# ---------------------------------------------------------------------------
# Event statistics sub-models (02C)
# ---------------------------------------------------------------------------


class EventStatisticVariableConfig(BaseModel):
    """Configuration for one weather driver variable used in event statistic calculations.

    Attributes
    ----------
    variable_name:
        Name of the variable in the weather time series NetCDF (e.g. ``"mm_per_hr"``).
    units:
        Units of the variable. Currently supported: ``"mm_per_hr"`` (precip intensity),
        ``"m"`` (water level / stage).
    max_intensity_windows_min:
        List of rolling-window durations in minutes over which to compute the maximum
        accumulated intensity (e.g. ``[5, 30, 60, 1440]`` for 5-min through 24-hour
        windows). Pass ``null`` (``None``) to take the simple maximum over all timesteps
        without any rolling window — appropriate for boundary stage variables where the
        peak instantaneous value is the statistic of interest.
    """

    variable_name: str
    units: str
    max_intensity_windows_min: list[int] | None


class EventStatisticsConfig(BaseModel):
    """Configuration for event statistic computation.

    Required on the primary (non-comparative) ssfha analysis. Defines which weather
    driver variables are used when computing univariate and multivariate event return
    periods. Event return periods are always computed once, at the primary analysis
    level, and shared with any comparative analyses.

    Attributes
    ----------
    precip_intensity:
        Precipitation intensity variable. Required.
    boundary_stage:
        Boundary condition stage variable (e.g. storm tide / surge). Optional —
        omit for rain-only analyses.
    """

    precip_intensity: EventStatisticVariableConfig
    boundary_stage: EventStatisticVariableConfig | None = None


class SlurmConfig(BaseModel):
    partition: str
    account: str
    time_min_per_job: int
    mem_gb_per_cpu: int = 2
    cpus_per_task: int = 1
    additional_sbatch_params: list[str] | None = None


class ExecutionConfig(BaseModel):
    mode: Literal["local_concurrent", "slurm"]
    max_workers: int | None = None
    slurm: SlurmConfig | None = None

    @model_validator(mode="after")
    def validate_slurm_required_if_slurm_mode(self) -> ExecutionConfig:
        if self.mode == "slurm" and self.slurm is None:
            raise ConfigurationError(
                field="execution.slurm",
                message="'slurm' config section is required when mode='slurm'.",
            )
        return self


# ---------------------------------------------------------------------------
# SsfhaConfig
# ---------------------------------------------------------------------------


class SsfhaConfig(BaseModel):
    fha_approach: Literal["ssfha"]
    fha_id: str
    project_name: str
    is_comparative_analysis: bool = False
    output_dir: Path | None = None
    study_area_config: Path | None = None
    n_years_synthesized: int
    return_periods: list[int]
    alpha: float
    beta: float
    toggle_uncertainty: bool
    toggle_mcds: bool
    toggle_ppcct: bool
    toggle_flood_risk: bool
    toggle_design_comparison: bool
    alt_fha_analyses: list[Path] = Field(default_factory=list)
    weather_event_indices: list[str] | None = None
    triton_outputs: TritonOutputsConfig
    event_data: EventDataConfig
    event_statistic_variables: EventStatisticsConfig | None = None
    uncertainty: UncertaintyConfig | None = None
    ppcct: PPCCTConfig | None = None
    flood_risk: FloodRiskConfig | None = None
    execution: ExecutionConfig

    @model_validator(mode="after")
    def validate_toggle_dependencies(self) -> SsfhaConfig:
        errors: list[str] = []

        # --- Comparative analysis: forbidden fields ---
        if self.is_comparative_analysis:
            if self.event_statistic_variables is not None:
                errors.append(
                    "is_comparative_analysis=True but 'event_statistic_variables' is set. "
                    "Event statistics belong to the primary analysis only."
                )
            if self.alt_fha_analyses:
                errors.append(
                    "is_comparative_analysis=True but 'alt_fha_analyses' is non-empty. "
                    "Comparative analyses cannot themselves reference further comparative analyses."
                )
            if self.toggle_mcds:
                errors.append(
                    "is_comparative_analysis=True but toggle_mcds=True. MCDS is only valid on the primary analysis."
                )

        # --- Primary ssfha analysis: required fields ---
        if not self.is_comparative_analysis:
            if self.weather_event_indices is None:
                errors.append(
                    "is_comparative_analysis=False but 'weather_event_indices' is not set. "
                    "Required for all primary ssfha analyses."
                )
            else:
                # Validate that a year-like index is present
                has_year = any(idx in WEATHER_EVENT_INDEX_YEAR_ALIASES for idx in self.weather_event_indices)
                if not has_year:
                    errors.append(
                        f"'weather_event_indices' must include a year index "
                        f"(one of: {sorted(WEATHER_EVENT_INDEX_YEAR_ALIASES)}). "
                        f"Got: {self.weather_event_indices}"
                    )

            if self.event_statistic_variables is None:
                errors.append(
                    "is_comparative_analysis=False but 'event_statistic_variables' is not set. "
                    "Required for all primary ssfha analyses."
                )

        # --- Toggle dependencies ---
        if self.toggle_uncertainty and self.uncertainty is None:
            errors.append("toggle_uncertainty=True but 'uncertainty' config section is missing")

        if self.toggle_ppcct:
            if self.ppcct is None:
                errors.append("toggle_ppcct=True but 'ppcct' config section is missing")
            if self.triton_outputs.observed is None:
                errors.append("toggle_ppcct=True but 'triton_outputs.observed' is not set")
            if self.event_data.obs_event_summaries is None:
                errors.append("toggle_ppcct=True but 'event_data.obs_event_summaries' is not set")

        if self.toggle_design_comparison and not self.alt_fha_analyses:
            errors.append("toggle_design_comparison=True but 'alt_fha_analyses' is empty")

        if errors:
            raise ConfigurationError(
                field="toggle_dependencies",
                message="; ".join(errors),
            )

        return self


# ---------------------------------------------------------------------------
# BdsConfig
# ---------------------------------------------------------------------------


class BdsConfig(BaseModel):
    fha_approach: Literal["bds"]
    fha_id: str
    project_name: str
    is_comparative_analysis: bool = False
    output_dir: Path | None = None
    study_area_config: Path | None = None
    return_periods: list[int]
    toggle_ppcct: bool
    toggle_flood_risk: bool
    design_storm_output: Path
    design_storm_timeseries: Path
    ppcct: PPCCTConfig | None = None
    flood_risk: FloodRiskConfig | None = None
    execution: ExecutionConfig

    @model_validator(mode="after")
    def validate_toggle_dependencies(self) -> BdsConfig:
        errors: list[str] = []

        if self.toggle_ppcct:
            if self.ppcct is None:
                errors.append("toggle_ppcct=True but 'ppcct' config section is missing")

        if errors:
            raise ConfigurationError(
                field="toggle_dependencies",
                message="; ".join(errors),
            )

        return self


# ---------------------------------------------------------------------------
# Discriminated union — top-level analysis config type
# ---------------------------------------------------------------------------

SSFHAConfig = Annotated[
    SsfhaConfig | BdsConfig,
    Field(discriminator="fha_approach"),
]
