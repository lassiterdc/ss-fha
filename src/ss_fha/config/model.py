"""Pydantic v2 configuration models for ss-fha.

Two top-level models:
  - SystemConfig  — fixed geographic context for a study area (system.yaml)
  - SSFHAConfig   — discriminated union on fha_approach (analysis_*.yaml)
      SsfhaConfig  (fha_approach="ssfha")
      BdsConfig    (fha_approach="bds")

Existence checks for Path fields are deferred to validation.py (01E).
This module validates structure, types, and toggle-dependency consistency only.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, Field, model_validator

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
    def validate_fema_fields_paired(self) -> "SystemConfig":
        raster = self.geospatial.fema_flood_raster
        return_pd = self.geospatial.fema_flood_raster_return_period_yr
        if (raster is None) != (return_pd is None):
            missing = (
                "fema_flood_raster_return_period_yr"
                if raster is not None
                else "fema_flood_raster"
            )
            provided = (
                "fema_flood_raster"
                if raster is not None
                else "fema_flood_raster_return_period_yr"
            )
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


class EventDataConfig(BaseModel):
    sim_event_summaries: Path
    sim_event_timeseries: Path | None = None
    sim_event_iloc_mapping: Path | None = None
    obs_event_summaries: Path | None = None
    obs_event_timeseries: Path | None = None
    obs_event_iloc_mapping: Path | None = None


class PPCCTConfig(BaseModel):
    n_years_observed: int


class FloodRiskConfig(BaseModel):
    """Flood risk assessment configuration (fields added in chunk 01E / Phase 3F)."""
    pass


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
    def validate_slurm_required_if_slurm_mode(self) -> "ExecutionConfig":
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
    output_dir: Path | None = None
    study_area_config: Path | None = None
    n_years_synthesized: int
    return_periods: list[int]
    toggle_uncertainty: bool
    toggle_mcds: bool
    toggle_ppcct: bool
    toggle_flood_risk: bool
    toggle_design_comparison: bool
    alt_fha_analyses: list[Path] = Field(default_factory=list)
    triton_outputs: TritonOutputsConfig
    event_data: EventDataConfig
    ppcct: PPCCTConfig | None = None
    flood_risk: FloodRiskConfig | None = None
    execution: ExecutionConfig

    @model_validator(mode="after")
    def validate_toggle_dependencies(self) -> "SsfhaConfig":
        errors: list[str] = []

        if self.toggle_ppcct:
            if self.ppcct is None:
                errors.append(
                    "toggle_ppcct=True but 'ppcct' config section is missing"
                )
            if self.triton_outputs.observed is None:
                errors.append(
                    "toggle_ppcct=True but 'triton_outputs.observed' is not set"
                )
            if self.event_data.obs_event_summaries is None:
                errors.append(
                    "toggle_ppcct=True but 'event_data.obs_event_summaries' is not set"
                )

        if self.toggle_design_comparison and not self.alt_fha_analyses:
            errors.append(
                "toggle_design_comparison=True but 'alt_fha_analyses' is empty"
            )

        if self.toggle_mcds and self.fha_approach != "ssfha":
            errors.append(
                "toggle_mcds=True is only valid when fha_approach='ssfha'"
            )

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
    def validate_toggle_dependencies(self) -> "BdsConfig":
        errors: list[str] = []

        if self.toggle_ppcct:
            if self.ppcct is None:
                errors.append(
                    "toggle_ppcct=True but 'ppcct' config section is missing"
                )

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
