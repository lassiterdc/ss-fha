"""Business logic validation for ss-fha configurations.

Validates that a config makes sense for a real run — files exist, workflow
inputs are complete for enabled toggles, etc. This is the layer beyond Pydantic
type checking: Pydantic validates structure; this module validates reality.

All validators accumulate every issue before raising, so users see the complete
list of problems at once rather than fixing them one at a time.

Primary entry point:
    preflight_validate(config, system_config) -> ValidationResult

Each validate_* function returns a ValidationResult; preflight_validate merges
them and calls raise_if_invalid().
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ss_fha.config.model import BdsConfig, SsfhaConfig, SystemConfig
from ss_fha.exceptions import SSFHAValidationError

# SSFHAConfig is a type alias (Annotated union), not a class — use the concrete
# types directly in function signatures where needed, or accept Union[SsfhaConfig, BdsConfig].
from typing import Union

SSFHAConfig = Union[SsfhaConfig, BdsConfig]


# ---------------------------------------------------------------------------
# Core data structures
# ---------------------------------------------------------------------------

@dataclass
class ValidationIssue:
    """A single validation failure.

    Attributes:
        field: Dotted config field path (e.g., "triton_outputs.combined")
        message: What is wrong
        current_value: The field's current value (for context in error output)
        fix_hint: Actionable guidance — what the user must do to fix the problem
    """

    field: str
    message: str
    current_value: Any
    fix_hint: str

    def __str__(self) -> str:
        lines = [
            f"{self.field}: {self.message}",
            f"  Current value: {self.current_value!r}",
            f"  Fix: {self.fix_hint}",
        ]
        return "\n".join(lines)


@dataclass
class ValidationResult:
    """Accumulated result of one or more validation passes.

    Attributes:
        is_valid: True if no issues were recorded
        issues: List of all ValidationIssue objects found
    """

    issues: list[ValidationIssue] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        """True only when no issues have been recorded."""
        return len(self.issues) == 0

    def add_issue(
        self,
        field_name: str,
        message: str,
        current_value: Any,
        fix_hint: str,
    ) -> None:
        """Record a validation issue."""
        self.issues.append(
            ValidationIssue(
                field=field_name,
                message=message,
                current_value=current_value,
                fix_hint=fix_hint,
            )
        )

    def merge(self, other: ValidationResult) -> ValidationResult:
        """Merge issues from another ValidationResult into this one.

        Returns self to allow chaining.
        """
        self.issues.extend(other.issues)
        return self

    def raise_if_invalid(self) -> None:
        """Raise SSFHAValidationError if any issues were recorded.

        The error contains every issue formatted as a human-readable string,
        so the user sees the complete list of problems in one exception.

        Raises:
            SSFHAValidationError: If is_valid is False
        """
        if not self.is_valid:
            formatted = [str(issue) for issue in self.issues]
            raise SSFHAValidationError(issues=formatted)


# ---------------------------------------------------------------------------
# validate_config — structural / logical checks (no filesystem access)
# ---------------------------------------------------------------------------

def validate_config(config: SSFHAConfig) -> ValidationResult:
    """Validate structural and logical consistency of an analysis config.

    Checks that field combinations make sense independent of filesystem state.
    (Toggle-dependency checks are already enforced by Pydantic model_validators;
    this function catches additional cross-field logic not expressible in Pydantic.)

    Args:
        config: A parsed SsfhaConfig or BdsConfig instance.

    Returns:
        ValidationResult accumulating any issues found.
    """
    result = ValidationResult()

    if config.return_periods and len(config.return_periods) == 0:
        result.add_issue(
            field_name="return_periods",
            message="return_periods list must not be empty",
            current_value=config.return_periods,
            fix_hint="Add at least one return period (e.g., [1, 2, 10, 100])",
        )

    if isinstance(config, SsfhaConfig):
        if config.n_years_synthesized <= 0:
            result.add_issue(
                field_name="n_years_synthesized",
                message="n_years_synthesized must be a positive integer",
                current_value=config.n_years_synthesized,
                fix_hint="Set n_years_synthesized to the number of years in the synthetic weather record (e.g., 1000)",
            )

        if config.toggle_ppcct and config.ppcct is not None:
            if config.ppcct.n_years_observed <= 0:
                result.add_issue(
                    field_name="ppcct.n_years_observed",
                    message="n_years_observed must be a positive integer",
                    current_value=config.ppcct.n_years_observed,
                    fix_hint="Set n_years_observed to the number of years in the observed record (e.g., 18)",
                )

    return result


# ---------------------------------------------------------------------------
# validate_input_files — file existence checks
# ---------------------------------------------------------------------------

def validate_input_files(
    config: SSFHAConfig,
    system_config: SystemConfig,
) -> ValidationResult:
    """Validate that all referenced input files and directories exist.

    Paths are resolved against project_dir (config.output_dir.parent if
    output_dir is set, otherwise left as-is) before checking existence.
    Uses Path.exists() for all checks so zarr stores (directories) are handled
    correctly alongside regular files.

    Args:
        config: A parsed SsfhaConfig or BdsConfig instance.
        system_config: The corresponding SystemConfig instance.

    Returns:
        ValidationResult accumulating any missing-path issues.
    """
    result = ValidationResult()

    # Determine base directory for resolving relative paths.
    # output_dir is set to the yaml parent by the loader, so its parent is the
    # case study directory — the natural root for relative input paths.
    base_dir: Path | None = None
    if config.output_dir is not None:
        base_dir = config.output_dir.parent

    def _resolve(p: Path) -> Path:
        if base_dir is not None and not p.is_absolute():
            return base_dir / p
        return p

    def _check(path: Path, field_name: str, description: str) -> None:
        resolved = _resolve(path)
        if not resolved.exists():
            result.add_issue(
                field_name=field_name,
                message=f"{description} does not exist",
                current_value=str(path),
                fix_hint=(
                    f"Ensure the file or directory exists at: {resolved}. "
                    "If the path is relative, it is resolved against the case study directory."
                ),
            )

    # --- System config paths ---
    _check(system_config.geospatial.watershed, "geospatial.watershed", "Watershed shapefile")

    optional_geo = {
        "geospatial.roads": system_config.geospatial.roads,
        "geospatial.sidewalks": system_config.geospatial.sidewalks,
        "geospatial.buildings": system_config.geospatial.buildings,
        "geospatial.parcels": system_config.geospatial.parcels,
        "geospatial.fema_flood_raster": system_config.geospatial.fema_flood_raster,
    }
    for fname, fpath in optional_geo.items():
        if fpath is not None:
            _check(fpath, fname, fname.split(".")[-1].replace("_", " ").title())

    # --- Analysis config paths (common to both SsfhaConfig and BdsConfig) ---
    if config.study_area_config is not None:
        _check(config.study_area_config, "study_area_config", "Study area config YAML")

    if isinstance(config, SsfhaConfig):
        _check(
            config.triton_outputs.combined,
            "triton_outputs.combined",
            "Combined TRITON output zarr store",
        )
        if config.triton_outputs.observed is not None:
            _check(
                config.triton_outputs.observed,
                "triton_outputs.observed",
                "Observed TRITON output zarr store",
            )
        _check(
            config.event_data.sim_event_summaries,
            "event_data.sim_event_summaries",
            "Simulated event summaries CSV",
        )
        optional_event = {
            "event_data.sim_event_timeseries": config.event_data.sim_event_timeseries,
            "event_data.sim_event_iloc_mapping": config.event_data.sim_event_iloc_mapping,
            "event_data.obs_event_summaries": config.event_data.obs_event_summaries,
            "event_data.obs_event_timeseries": config.event_data.obs_event_timeseries,
            "event_data.obs_event_iloc_mapping": config.event_data.obs_event_iloc_mapping,
        }
        for fname, fpath in optional_event.items():
            if fpath is not None:
                _check(fpath, fname, fname.split(".")[-1].replace("_", " ").title())

        for i, alt_path in enumerate(config.alt_fha_analyses):
            _check(alt_path, f"alt_fha_analyses[{i}]", f"Alternative FHA analysis config [{i}]")

    elif isinstance(config, BdsConfig):
        _check(
            config.design_storm_output,
            "design_storm_output",
            "BDS design storm output zarr store",
        )
        _check(
            config.design_storm_timeseries,
            "design_storm_timeseries",
            "BDS design storm timeseries CSV",
        )

    return result


# ---------------------------------------------------------------------------
# validate_workflow_inputs — per-workflow input completeness
# ---------------------------------------------------------------------------

def validate_workflow_inputs(config: SSFHAConfig) -> ValidationResult:
    """Validate that each enabled workflow has all required inputs specified.

    Checks that the fields required by enabled toggle combinations are present.
    Note: Pydantic model_validators already enforce many of these. This function
    catches runtime-discoverable issues that Pydantic cannot check at parse time
    (e.g., None checks on fields that are structurally optional but workflow-required).

    Args:
        config: A parsed SsfhaConfig or BdsConfig instance.

    Returns:
        ValidationResult accumulating any missing-input issues.
    """
    result = ValidationResult()

    if not isinstance(config, SsfhaConfig):
        # BdsConfig toggle dependencies are fully handled by Pydantic
        return result

    # PPCCT workflow: requires observed zarr, ppcct section, obs event summaries
    if config.toggle_ppcct:
        # These are already enforced by Pydantic, but validate defensively in
        # case the config was constructed directly (not via load_config_from_dict)
        if config.triton_outputs.observed is None:
            result.add_issue(
                field_name="triton_outputs.observed",
                message="Required for PPCCT validation (toggle_ppcct=True)",
                current_value=None,
                fix_hint="Set triton_outputs.observed to the path of the observed TRITON output zarr store",
            )
        if config.ppcct is None:
            result.add_issue(
                field_name="ppcct",
                message="Required for PPCCT validation (toggle_ppcct=True)",
                current_value=None,
                fix_hint="Add a 'ppcct' config section with n_years_observed",
            )
        if config.event_data.obs_event_summaries is None:
            result.add_issue(
                field_name="event_data.obs_event_summaries",
                message="Required for PPCCT validation (toggle_ppcct=True)",
                current_value=None,
                fix_hint="Set event_data.obs_event_summaries to the path of the observed event summaries CSV",
            )

    # FHA comparison workflow: requires at least one alternative analysis
    if config.toggle_design_comparison and not config.alt_fha_analyses:
        result.add_issue(
            field_name="alt_fha_analyses",
            message="Required for FHA comparison (toggle_design_comparison=True)",
            current_value=[],
            fix_hint="Add at least one path to alt_fha_analyses pointing to an alternative FHA config YAML",
        )

    # Flood risk: FloodRiskConfig sub-section must be present
    if config.toggle_flood_risk and config.flood_risk is None:
        result.add_issue(
            field_name="flood_risk",
            message="Required for flood risk assessment (toggle_flood_risk=True)",
            current_value=None,
            fix_hint="Add a 'flood_risk' config section (fields to be defined in Phase 3F)",
        )

    return result


# ---------------------------------------------------------------------------
# preflight_validate — primary entry point
# ---------------------------------------------------------------------------

def preflight_validate(
    config: SSFHAConfig,
    system_config: SystemConfig,
) -> ValidationResult:
    """Run all validation checks and raise if any issues are found.

    This is the single entry point called before any workflow execution.
    Combines structural, file-existence, and per-workflow checks into one
    consolidated ValidationResult, then raises if anything is wrong.

    Args:
        config: A parsed SsfhaConfig or BdsConfig instance.
        system_config: The corresponding SystemConfig instance.

    Returns:
        ValidationResult — only returned if fully valid (no issues).

    Raises:
        SSFHAValidationError: If any validation issue is found, with all issues
            listed in the exception message.
    """
    result = ValidationResult()
    result.merge(validate_config(config))
    result.merge(validate_input_files(config, system_config))
    result.merge(validate_workflow_inputs(config))
    result.raise_if_invalid()
    return result
