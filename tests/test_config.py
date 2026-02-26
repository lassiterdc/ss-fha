"""Tests for ss_fha.config and ss_fha.exceptions (Work Chunks 01A, 01B)."""

from pathlib import Path


# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

def test_defaults_are_accessible():
    """All default constants can be imported and have the expected types."""
    from ss_fha.config.defaults import (
        DEFAULT_BOOTSTRAP_CI_ALPHA,
        DEFAULT_DEPTH_THRESHOLDS_M,
        DEFAULT_N_BOOTSTRAP_SAMPLES,
        DEFAULT_PLOTTING_POSITION_METHOD,
        DEFAULT_RETURN_PERIODS,
        DEFAULT_VAR_NAMES,
    )

    assert isinstance(DEFAULT_RETURN_PERIODS, list)
    assert all(isinstance(rp, int) for rp in DEFAULT_RETURN_PERIODS)
    assert DEFAULT_RETURN_PERIODS == [1, 2, 10, 100]

    assert isinstance(DEFAULT_DEPTH_THRESHOLDS_M, list)
    assert all(isinstance(t, float) for t in DEFAULT_DEPTH_THRESHOLDS_M)

    assert isinstance(DEFAULT_N_BOOTSTRAP_SAMPLES, int)
    assert DEFAULT_N_BOOTSTRAP_SAMPLES > 0

    assert isinstance(DEFAULT_PLOTTING_POSITION_METHOD, tuple)
    assert len(DEFAULT_PLOTTING_POSITION_METHOD) == 2

    assert isinstance(DEFAULT_BOOTSTRAP_CI_ALPHA, float)
    assert 0.0 < DEFAULT_BOOTSTRAP_CI_ALPHA < 1.0

    assert isinstance(DEFAULT_VAR_NAMES, dict)
    assert "flood_depth" in DEFAULT_VAR_NAMES


# ---------------------------------------------------------------------------
# Exceptions — import check
# ---------------------------------------------------------------------------

def test_exceptions_importable():
    """All required exception classes can be imported from ss_fha.exceptions."""
    from ss_fha.exceptions import (  # noqa: F401
        BootstrapError,
        ConfigurationError,
        DataError,
        SSFHAError,
        SSFHAValidationError,
        WorkflowError,
    )


# ---------------------------------------------------------------------------
# Exceptions — attribute checks
# ---------------------------------------------------------------------------

def test_exceptions_have_attributes():
    """Each exception stores the contextual attributes specified in the plan."""
    from ss_fha.exceptions import (
        BootstrapError,
        ConfigurationError,
        DataError,
        SSFHAValidationError,
        WorkflowError,
    )

    # ConfigurationError
    err = ConfigurationError(field="n_years_synthesized", message="Required field is missing.")
    assert err.field == "n_years_synthesized"
    assert "n_years_synthesized" in str(err)
    assert "Required field is missing." in str(err)

    # DataError
    err = DataError(
        operation="load zarr",
        filepath=Path("/data/combined.zarr"),
        reason="file not found",
    )
    assert err.operation == "load zarr"
    assert err.filepath == Path("/data/combined.zarr")
    assert err.reason == "file not found"
    assert "load zarr" in str(err)
    assert "/data/combined.zarr" in str(err)
    assert "file not found" in str(err)

    # BootstrapError
    err = BootstrapError(sample_id=42, reason="empty resample")
    assert err.sample_id == 42
    assert err.reason == "empty resample"
    assert "42" in str(err)
    assert "empty resample" in str(err)

    # WorkflowError
    err = WorkflowError(phase="flood_hazard", stderr="snakemake traceback here")
    assert err.phase == "flood_hazard"
    assert err.stderr == "snakemake traceback here"
    assert "flood_hazard" in str(err)
    assert "snakemake traceback here" in str(err)

    # SSFHAValidationError
    issues = ["return_periods must not be empty", "n_years_synthesized must be > 0"]
    err = SSFHAValidationError(issues=issues)
    assert err.issues == issues
    assert "2 issue(s)" in str(err)
    for issue in issues:
        assert issue in str(err)


def test_exception_hierarchy():
    """All ss-fha exceptions are catchable as SSFHAError."""
    from ss_fha.exceptions import (
        BootstrapError,
        ConfigurationError,
        DataError,
        SSFHAError,
        SSFHAValidationError,
        WorkflowError,
    )

    exception_types = [
        ConfigurationError("field", "msg"),
        DataError("op", Path("/some/file.zarr"), "reason"),
        BootstrapError(0, "reason"),
        WorkflowError("phase", "stderr output"),
        SSFHAValidationError(["issue"]),
    ]

    for exc in exception_types:
        assert isinstance(exc, SSFHAError), (
            f"{type(exc).__name__} should inherit from SSFHAError"
        )


# ===========================================================================
# Phase 1B — Config model and loader
# ===========================================================================

# Minimal valid dicts for smoke tests

_MINIMAL_SSFHA_DICT = {
    "fha_id": "test_ssfha",
    "fha_approach": "ssfha",
    "project_name": "test_project",
    "n_years_synthesized": 1000,
    "return_periods": [1, 2, 10, 100],
    "toggle_uncertainty": False,
    "toggle_mcds": False,
    "toggle_ppcct": False,
    "toggle_flood_risk": False,
    "toggle_design_comparison": False,
    "triton_outputs": {"combined": "/tmp/fake_combined.zarr"},
    "event_data": {"sim_event_summaries": "/tmp/fake_summaries.csv"},
    "execution": {"mode": "local_concurrent"},
}

_MINIMAL_BDS_DICT = {
    "fha_id": "test_bds",
    "fha_approach": "bds",
    "project_name": "test_project",
    "return_periods": [1, 2, 10, 100],
    "toggle_ppcct": False,
    "toggle_flood_risk": False,
    "design_storm_output": "/tmp/fake_bds.zarr",
    "design_storm_timeseries": "/tmp/fake_ts.csv",
    "execution": {"mode": "local_concurrent"},
}

_MINIMAL_SYSTEM_DICT = {
    "study_area_id": "test_area",
    "crs_epsg": 32147,
    "geospatial": {
        "watershed": "/tmp/fake_watershed.shp",
    },
}


# ---------------------------------------------------------------------------
# Model imports
# ---------------------------------------------------------------------------

def test_model_importable():
    """All config model classes and loader functions can be imported."""
    from ss_fha.config import (  # noqa: F401
        BdsConfig,
        EventDataConfig,
        ExecutionConfig,
        FloodRiskConfig,
        GeospatialConfig,
        PPCCTConfig,
        SSFHAConfig,
        SlurmConfig,
        SsfhaConfig,
        SystemConfig,
        TritonOutputsConfig,
        load_config,
        load_config_from_dict,
        load_system_config,
    )


# ---------------------------------------------------------------------------
# Minimal config loads
# ---------------------------------------------------------------------------

def test_minimal_ssfha_config_loads():
    """Minimal SsfhaConfig (all toggles off) loads without error."""
    from ss_fha.config import load_config_from_dict, SsfhaConfig
    cfg = load_config_from_dict(_MINIMAL_SSFHA_DICT)
    assert isinstance(cfg, SsfhaConfig)
    assert cfg.fha_id == "test_ssfha"
    assert cfg.fha_approach == "ssfha"
    assert cfg.n_years_synthesized == 1000


def test_minimal_bds_config_loads():
    """Minimal BdsConfig loads without error."""
    from ss_fha.config import load_config_from_dict, BdsConfig
    cfg = load_config_from_dict(_MINIMAL_BDS_DICT)
    assert isinstance(cfg, BdsConfig)
    assert cfg.fha_id == "test_bds"
    assert cfg.fha_approach == "bds"


def test_minimal_system_config_loads():
    """Minimal SystemConfig loads without error."""
    from ss_fha.config.model import SystemConfig
    cfg = SystemConfig.model_validate(_MINIMAL_SYSTEM_DICT)
    assert cfg.crs_epsg == 32147
    assert cfg.study_area_id == "test_area"


# ---------------------------------------------------------------------------
# Discriminated union
# ---------------------------------------------------------------------------

def test_discriminated_union_selects_correct_model():
    """load_config_from_dict selects SsfhaConfig vs BdsConfig by fha_approach."""
    from ss_fha.config import load_config_from_dict, SsfhaConfig, BdsConfig
    ssfha = load_config_from_dict(_MINIMAL_SSFHA_DICT)
    bds = load_config_from_dict(_MINIMAL_BDS_DICT)
    assert isinstance(ssfha, SsfhaConfig)
    assert isinstance(bds, BdsConfig)


def test_invalid_fha_approach_raises():
    """An unrecognised fha_approach raises an error at parse time."""
    import pytest
    from pydantic import ValidationError as PydanticValidationError
    from ss_fha.config import load_config_from_dict

    bad = dict(_MINIMAL_SSFHA_DICT, fha_approach="unknown_approach")
    with pytest.raises(PydanticValidationError):
        load_config_from_dict(bad)


def test_missing_fha_approach_raises_configuration_error():
    """Missing fha_approach key raises ConfigurationError."""
    import pytest
    from ss_fha.config import load_config_from_dict
    from ss_fha.exceptions import ConfigurationError

    d = dict(_MINIMAL_SSFHA_DICT)
    del d["fha_approach"]
    with pytest.raises(ConfigurationError):
        load_config_from_dict(d)


# ---------------------------------------------------------------------------
# Toggle dependency validation
# ---------------------------------------------------------------------------

def test_toggle_ppcct_requires_ppcct_section():
    """toggle_ppcct=True without a ppcct section raises ConfigurationError."""
    import pytest
    from ss_fha.config import load_config_from_dict
    from ss_fha.exceptions import ConfigurationError

    d = dict(_MINIMAL_SSFHA_DICT)
    d["toggle_ppcct"] = True
    d["triton_outputs"] = {"combined": "/tmp/c.zarr", "observed": "/tmp/o.zarr"}
    d["event_data"] = {
        "sim_event_summaries": "/tmp/s.csv",
        "obs_event_summaries": "/tmp/obs.csv",
    }
    # ppcct section still absent — should raise
    with pytest.raises(ConfigurationError):
        load_config_from_dict(d)


def test_toggle_ppcct_requires_observed_zarr():
    """toggle_ppcct=True without triton_outputs.observed raises ConfigurationError."""
    import pytest
    from ss_fha.config import load_config_from_dict
    from ss_fha.exceptions import ConfigurationError

    d = dict(_MINIMAL_SSFHA_DICT)
    d["toggle_ppcct"] = True
    d["ppcct"] = {"n_years_observed": 18}
    d["event_data"] = {
        "sim_event_summaries": "/tmp/s.csv",
        "obs_event_summaries": "/tmp/obs.csv",
    }
    # observed zarr absent
    with pytest.raises(ConfigurationError):
        load_config_from_dict(d)


def test_toggle_ppcct_all_present_passes():
    """toggle_ppcct=True with all required fields present loads successfully."""
    from ss_fha.config import load_config_from_dict

    d = dict(_MINIMAL_SSFHA_DICT)
    d["toggle_ppcct"] = True
    d["ppcct"] = {"n_years_observed": 18}
    d["triton_outputs"] = {"combined": "/tmp/c.zarr", "observed": "/tmp/o.zarr"}
    d["event_data"] = {
        "sim_event_summaries": "/tmp/s.csv",
        "obs_event_summaries": "/tmp/obs.csv",
    }
    cfg = load_config_from_dict(d)
    assert cfg.ppcct.n_years_observed == 18


def test_toggle_design_comparison_requires_alt_fha_analyses():
    """toggle_design_comparison=True without alt_fha_analyses raises ConfigurationError."""
    import pytest
    from ss_fha.config import load_config_from_dict
    from ss_fha.exceptions import ConfigurationError

    d = dict(_MINIMAL_SSFHA_DICT)
    d["toggle_design_comparison"] = True
    with pytest.raises(ConfigurationError):
        load_config_from_dict(d)


def test_toggle_validation_accumulates_errors():
    """Multiple toggle violations are reported together, not one at a time."""
    import pytest
    from ss_fha.config import load_config_from_dict
    from ss_fha.exceptions import ConfigurationError

    d = dict(_MINIMAL_SSFHA_DICT)
    d["toggle_ppcct"] = True          # missing ppcct section, observed zarr, obs_event_summaries
    d["toggle_design_comparison"] = True  # missing alt_fha_analyses
    with pytest.raises(ConfigurationError) as exc_info:
        load_config_from_dict(d)
    # All issues should be in the message
    msg = str(exc_info.value)
    assert "ppcct" in msg
    assert "alt_fha_analyses" in msg


# ---------------------------------------------------------------------------
# Required fields
# ---------------------------------------------------------------------------

def test_config_validates_required_fields():
    """Missing required fields raise pydantic.ValidationError."""
    import pytest
    from pydantic import ValidationError as PydanticValidationError
    from ss_fha.config import load_config_from_dict

    # n_years_synthesized is required on SsfhaConfig
    d = dict(_MINIMAL_SSFHA_DICT)
    del d["n_years_synthesized"]
    with pytest.raises(PydanticValidationError):
        load_config_from_dict(d)


def test_bds_has_no_toggle_uncertainty():
    """BdsConfig must not have a toggle_uncertainty field."""
    from ss_fha.config import BdsConfig
    assert not hasattr(BdsConfig.model_fields, "toggle_uncertainty") or \
           "toggle_uncertainty" not in BdsConfig.model_fields


# ---------------------------------------------------------------------------
# FEMA fields paired validation
# ---------------------------------------------------------------------------

def test_fema_fields_must_be_paired():
    """SystemConfig raises ConfigurationError if only one FEMA field is set."""
    import pytest
    from ss_fha.config.model import SystemConfig
    from ss_fha.exceptions import ConfigurationError

    # raster set, return period missing
    d = dict(_MINIMAL_SYSTEM_DICT)
    d["geospatial"] = {
        "watershed": "/tmp/wshed.shp",
        "fema_flood_raster": "/tmp/fema.tif",
    }
    with pytest.raises(ConfigurationError):
        SystemConfig.model_validate(d)

    # return period set, raster missing
    d["geospatial"] = {
        "watershed": "/tmp/wshed.shp",
        "fema_flood_raster_return_period_yr": 100,
    }
    with pytest.raises(ConfigurationError):
        SystemConfig.model_validate(d)


def test_fema_fields_both_set_passes():
    """SystemConfig with both FEMA fields set loads without error."""
    from ss_fha.config.model import SystemConfig

    d = dict(_MINIMAL_SYSTEM_DICT)
    d["geospatial"] = {
        "watershed": "/tmp/wshed.shp",
        "fema_flood_raster": "/tmp/fema.tif",
        "fema_flood_raster_return_period_yr": 100,
    }
    cfg = SystemConfig.model_validate(d)
    assert cfg.geospatial.fema_flood_raster_return_period_yr == 100


def test_fema_fields_both_none_passes():
    """SystemConfig with both FEMA fields absent (None) loads without error."""
    from ss_fha.config.model import SystemConfig

    cfg = SystemConfig.model_validate(_MINIMAL_SYSTEM_DICT)
    assert cfg.geospatial.fema_flood_raster is None
    assert cfg.geospatial.fema_flood_raster_return_period_yr is None


# ---------------------------------------------------------------------------
# Slurm mode requires slurm section
# ---------------------------------------------------------------------------

def test_slurm_mode_requires_slurm_section():
    """ExecutionConfig with mode='slurm' but no slurm section raises ConfigurationError."""
    import pytest
    from ss_fha.config import load_config_from_dict
    from ss_fha.exceptions import ConfigurationError

    d = dict(_MINIMAL_SSFHA_DICT)
    d["execution"] = {"mode": "slurm"}
    with pytest.raises(ConfigurationError):
        load_config_from_dict(d)


# ---------------------------------------------------------------------------
# output_dir loader behaviour
# ---------------------------------------------------------------------------

def test_output_dir_set_from_yaml_parent(tmp_path):
    """load_config sets output_dir to yaml_path.parent when not specified."""
    import yaml as _yaml
    from ss_fha.config import load_config

    yaml_data = dict(_MINIMAL_SSFHA_DICT)
    yaml_file = tmp_path / "analysis_test.yaml"
    yaml_file.write_text(_yaml.dump(yaml_data))

    cfg = load_config(yaml_file)
    assert cfg.output_dir == tmp_path


def test_output_dir_explicit_not_overridden(tmp_path):
    """load_config does not override an explicitly set output_dir."""
    import yaml as _yaml
    from pathlib import Path as _Path
    from ss_fha.config import load_config

    yaml_data = dict(_MINIMAL_SSFHA_DICT)
    yaml_data["output_dir"] = str(tmp_path / "custom_output")
    yaml_file = tmp_path / "analysis_test.yaml"
    yaml_file.write_text(_yaml.dump(yaml_data))

    cfg = load_config(yaml_file)
    assert cfg.output_dir == _Path(str(tmp_path / "custom_output"))


# ---------------------------------------------------------------------------
# YAML file loading (Norfolk case study YAMLs)
# ---------------------------------------------------------------------------

NORFOLK_CASE_DIR = Path(__file__).parents[1] / "cases" / "norfolk_ssfha_comparison"
NORFOLK_ANALYSIS_YAMLS = sorted(NORFOLK_CASE_DIR.glob("analysis_*.yaml"))


def test_norfolk_system_yaml_loads():
    """Norfolk system.yaml loads as SystemConfig without error."""
    from ss_fha.config import load_system_config
    cfg = load_system_config(NORFOLK_CASE_DIR / "system.yaml")
    assert cfg.crs_epsg == 32147
    assert cfg.study_area_id == "norfolk_va"


import pytest as _pytest

@_pytest.mark.parametrize("yaml_path", NORFOLK_ANALYSIS_YAMLS, ids=lambda p: p.stem)
def test_norfolk_case_yamls_load(yaml_path):
    """Each Norfolk analysis YAML loads without error via load_config."""
    from ss_fha.config import load_config
    cfg = load_config(yaml_path)
    assert cfg.fha_id is not None
    assert cfg.fha_approach in ("ssfha", "bds")


# ===========================================================================
# Phase 1E — Validation layer
# ===========================================================================

def _make_system_config(tmp_path):
    """Return a minimal SystemConfig whose watershed path actually exists."""
    from ss_fha.config.model import SystemConfig

    wshed = tmp_path / "watershed.shp"
    wshed.touch()
    return SystemConfig.model_validate({
        "study_area_id": "test_area",
        "crs_epsg": 32147,
        "geospatial": {"watershed": str(wshed)},
    })


def _make_ssfha_config(tmp_path, *, make_files: bool = True):
    """Return a minimal SsfhaConfig with paths inside tmp_path.

    When make_files=True, the referenced paths are created so file-existence
    checks pass. When make_files=False, the paths are declared but do not exist,
    allowing missing-file tests.
    """
    from ss_fha.config import load_config_from_dict

    combined = tmp_path / "combined.zarr"
    summaries = tmp_path / "summaries.csv"
    if make_files:
        combined.mkdir()   # zarr stores are directories
        summaries.touch()

    return load_config_from_dict({
        "fha_id": "test_ssfha",
        "fha_approach": "ssfha",
        "project_name": "test_project",
        "output_dir": str(tmp_path / "output"),
        "n_years_synthesized": 1000,
        "return_periods": [1, 2, 10, 100],
        "toggle_uncertainty": False,
        "toggle_mcds": False,
        "toggle_ppcct": False,
        "toggle_flood_risk": False,
        "toggle_design_comparison": False,
        "triton_outputs": {"combined": str(combined)},
        "event_data": {"sim_event_summaries": str(summaries)},
        "execution": {"mode": "local_concurrent"},
    })


# ---------------------------------------------------------------------------
# Validation module imports
# ---------------------------------------------------------------------------

def test_validation_importable():
    """All public names from ss_fha.validation can be imported."""
    from ss_fha.validation import (  # noqa: F401
        ValidationIssue,
        ValidationResult,
        preflight_validate,
        validate_config,
        validate_input_files,
        validate_workflow_inputs,
    )


# ---------------------------------------------------------------------------
# ValidationResult / ValidationIssue unit tests
# ---------------------------------------------------------------------------

def test_validation_result_starts_valid():
    """An empty ValidationResult is valid."""
    from ss_fha.validation import ValidationResult
    result = ValidationResult()
    assert result.is_valid
    assert result.issues == []


def test_validation_result_add_issue_marks_invalid():
    """Adding an issue makes is_valid False."""
    from ss_fha.validation import ValidationResult
    result = ValidationResult()
    result.add_issue(
        field_name="some_field",
        message="it is broken",
        current_value=None,
        fix_hint="Fix it.",
    )
    assert not result.is_valid
    assert len(result.issues) == 1


def test_validation_result_merge():
    """merge() combines issues from two ValidationResults."""
    from ss_fha.validation import ValidationResult
    a = ValidationResult()
    a.add_issue("field_a", "msg_a", None, "fix_a")
    b = ValidationResult()
    b.add_issue("field_b", "msg_b", None, "fix_b")
    a.merge(b)
    assert len(a.issues) == 2
    fields = {i.field for i in a.issues}
    assert fields == {"field_a", "field_b"}


def test_validation_result_raise_if_invalid_raises():
    """raise_if_invalid() raises SSFHAValidationError when issues exist."""
    import pytest
    from ss_fha.validation import ValidationResult
    from ss_fha.exceptions import SSFHAValidationError
    result = ValidationResult()
    result.add_issue("f", "m", "v", "h")
    with pytest.raises(SSFHAValidationError):
        result.raise_if_invalid()


def test_validation_result_raise_if_invalid_silent_when_valid():
    """raise_if_invalid() does not raise when there are no issues."""
    from ss_fha.validation import ValidationResult
    result = ValidationResult()
    result.raise_if_invalid()  # must not raise


def test_validation_issue_str_contains_key_fields():
    """ValidationIssue.__str__ includes field, message, current_value, and fix_hint."""
    from ss_fha.validation import ValidationIssue
    issue = ValidationIssue(
        field="triton_outputs.combined",
        message="does not exist",
        current_value="/some/path.zarr",
        fix_hint="Create the zarr store at the specified path.",
    )
    s = str(issue)
    assert "triton_outputs.combined" in s
    assert "does not exist" in s
    assert "/some/path.zarr" in s
    assert "Create the zarr store" in s


# ---------------------------------------------------------------------------
# test_validation_missing_input_files
# ---------------------------------------------------------------------------

def test_validation_missing_input_files(tmp_path):
    """preflight_validate reports all missing files, not just the first."""
    import pytest
    from ss_fha.validation import validate_input_files
    from ss_fha.config import load_config_from_dict
    from ss_fha.config.model import SystemConfig

    # System config pointing to a non-existent watershed
    system_cfg = SystemConfig.model_validate({
        "study_area_id": "test_area",
        "crs_epsg": 32147,
        "geospatial": {
            "watershed": str(tmp_path / "missing_watershed.shp"),
            "roads": str(tmp_path / "missing_roads.shp"),
        },
    })

    # Analysis config with non-existent combined zarr and summaries csv
    analysis_cfg = load_config_from_dict({
        "fha_id": "test_ssfha",
        "fha_approach": "ssfha",
        "project_name": "test_project",
        "output_dir": str(tmp_path / "output"),
        "n_years_synthesized": 1000,
        "return_periods": [1, 2, 10, 100],
        "toggle_uncertainty": False,
        "toggle_mcds": False,
        "toggle_ppcct": False,
        "toggle_flood_risk": False,
        "toggle_design_comparison": False,
        "triton_outputs": {"combined": str(tmp_path / "missing_combined.zarr")},
        "event_data": {"sim_event_summaries": str(tmp_path / "missing_summaries.csv")},
        "execution": {"mode": "local_concurrent"},
    })

    result = validate_input_files(analysis_cfg, system_cfg)
    assert not result.is_valid

    missing_fields = {issue.field for issue in result.issues}
    # All four missing paths should be reported together
    assert "geospatial.watershed" in missing_fields
    assert "geospatial.roads" in missing_fields
    assert "triton_outputs.combined" in missing_fields
    assert "event_data.sim_event_summaries" in missing_fields

    # fix_hint must be non-empty on every issue
    for issue in result.issues:
        assert issue.fix_hint, f"fix_hint is empty on issue: {issue.field}"


# ---------------------------------------------------------------------------
# test_validation_accumulates_errors
# ---------------------------------------------------------------------------

def test_validation_accumulates_errors(tmp_path):
    """Multiple issues across validate_* functions are all reported together."""
    import pytest
    from ss_fha.validation import preflight_validate
    from ss_fha.exceptions import SSFHAValidationError
    from ss_fha.config.model import SystemConfig
    from ss_fha.config import load_config_from_dict

    # System with missing watershed
    system_cfg = SystemConfig.model_validate({
        "study_area_id": "test_area",
        "crs_epsg": 32147,
        "geospatial": {"watershed": str(tmp_path / "missing.shp")},
    })

    # Analysis config: missing zarr + missing summaries
    analysis_cfg = load_config_from_dict({
        "fha_id": "test_ssfha",
        "fha_approach": "ssfha",
        "project_name": "test_project",
        "output_dir": str(tmp_path / "output"),
        "n_years_synthesized": 1000,
        "return_periods": [1, 2, 10, 100],
        "toggle_uncertainty": False,
        "toggle_mcds": False,
        "toggle_ppcct": False,
        "toggle_flood_risk": False,
        "toggle_design_comparison": False,
        "triton_outputs": {"combined": str(tmp_path / "missing.zarr")},
        "event_data": {"sim_event_summaries": str(tmp_path / "missing.csv")},
        "execution": {"mode": "local_concurrent"},
    })

    with pytest.raises(SSFHAValidationError) as exc_info:
        preflight_validate(analysis_cfg, system_cfg)

    # All three missing files should appear in the exception message
    msg = str(exc_info.value)
    assert "geospatial.watershed" in msg
    assert "triton_outputs.combined" in msg
    assert "event_data.sim_event_summaries" in msg
    # More than one issue reported
    assert exc_info.value.issues and len(exc_info.value.issues) >= 3


# ---------------------------------------------------------------------------
# test_validation_per_workflow
# ---------------------------------------------------------------------------

def test_validation_per_workflow(tmp_path):
    """validate_workflow_inputs catches missing PPCCT inputs when toggle_ppcct=True.

    This test constructs a SsfhaConfig directly (bypassing load_config_from_dict's
    Pydantic validators) to simulate a config with toggle_ppcct=True but missing
    observed zarr, ppcct section, and obs_event_summaries — verifying that
    validate_workflow_inputs catches all three.
    """
    from ss_fha.validation import validate_workflow_inputs
    from ss_fha.config.model import (
        SsfhaConfig, TritonOutputsConfig, EventDataConfig, ExecutionConfig
    )

    # Build a SsfhaConfig that passes Pydantic's toggle_ppcct checks, then
    # mutate the relevant fields to None to test defensive validation.
    cfg = SsfhaConfig.model_construct(
        fha_approach="ssfha",
        fha_id="test",
        project_name="test",
        output_dir=None,
        study_area_config=None,
        n_years_synthesized=1000,
        return_periods=[1, 2, 10, 100],
        toggle_uncertainty=False,
        toggle_mcds=False,
        toggle_ppcct=True,        # PPCCT enabled ...
        toggle_flood_risk=False,
        toggle_design_comparison=False,
        alt_fha_analyses=[],
        triton_outputs=TritonOutputsConfig.model_construct(
            combined=Path("/fake/combined.zarr"),
            observed=None,         # ... but observed is missing
        ),
        event_data=EventDataConfig.model_construct(
            sim_event_summaries=Path("/fake/summaries.csv"),
            obs_event_summaries=None,  # ... and obs summaries missing
        ),
        ppcct=None,                # ... and ppcct section missing
        flood_risk=None,
        execution=ExecutionConfig.model_construct(mode="local_concurrent", max_workers=None, slurm=None),
    )

    result = validate_workflow_inputs(cfg)
    assert not result.is_valid

    missing_fields = {issue.field for issue in result.issues}
    assert "triton_outputs.observed" in missing_fields
    assert "ppcct" in missing_fields
    assert "event_data.obs_event_summaries" in missing_fields


def test_validation_passes_for_valid_config(tmp_path):
    """preflight_validate returns a valid result when all paths exist and config is complete."""
    from ss_fha.validation import preflight_validate

    system_cfg = _make_system_config(tmp_path)
    analysis_cfg = _make_ssfha_config(tmp_path, make_files=True)

    result = preflight_validate(analysis_cfg, system_cfg)
    assert result.is_valid


# ===========================================================================
# Phase 1F — Test infrastructure
# ===========================================================================

def test_synthetic_test_case_builds(tmp_path):
    """build_minimal_test_case produces a valid, file-backed SSFHAConfig.

    Validates:
    - The returned object is a valid SSFHAConfig
    - The combined zarr store exists on disk with the correct variable
    - The sim event summaries CSV exists on disk with the expected index
    - assert_zarr_valid passes for the zarr store
    """
    from ss_fha.config import SsfhaConfig
    from tests.fixtures.test_case_builder import build_minimal_test_case
    from tests.utils_for_testing import assert_zarr_valid

    cfg = build_minimal_test_case(tmp_path)

    assert isinstance(cfg, SsfhaConfig)
    assert cfg.fha_approach == "ssfha"

    # zarr store exists and has the expected variable
    assert cfg.triton_outputs.combined.exists(), (
        f"combined.zarr not found at {cfg.triton_outputs.combined}"
    )
    assert_zarr_valid(
        path=cfg.triton_outputs.combined,
        expected_vars=["max_wlevel_m"],
    )

    # event summaries CSV exists and has the expected index columns
    import pandas as pd

    assert cfg.event_data.sim_event_summaries.exists(), (
        f"sim summaries CSV not found at {cfg.event_data.sim_event_summaries}"
    )
    df = pd.read_csv(cfg.event_data.sim_event_summaries, index_col=[0, 1, 2])
    assert "precip_depth_mm" in df.columns, (
        f"'precip_depth_mm' missing from summaries. Columns: {list(df.columns)}"
    )
    assert len(df) == 10, f"Expected 10 events, got {len(df)}"


# ===========================================================================
# Phase 1G — Case study config infrastructure
# ===========================================================================

_TEMPLATE_PATH = (
    Path(__file__).parents[1]
    / "src" / "ss_fha" / "examples" / "config_templates" / "norfolk_default.yaml"
)


def test_catalog_import_raises_before_id_populated():
    """NORFOLK_HYDROSHARE_RESOURCE_ID() raises ConfigurationError before ID is set."""
    import pytest
    from ss_fha.examples.case_study_catalog import NORFOLK_HYDROSHARE_RESOURCE_ID
    from ss_fha.exceptions import ConfigurationError

    with pytest.raises(ConfigurationError) as exc_info:
        NORFOLK_HYDROSHARE_RESOURCE_ID()
    assert "HydroShare" in str(exc_info.value)
    assert "06A" in str(exc_info.value)


def test_catalog_registry_has_norfolk():
    """CASE_STUDY_REGISTRY contains the norfolk_ssfha_comparison entry."""
    from ss_fha.examples.case_study_catalog import CASE_STUDY_REGISTRY

    assert "norfolk_ssfha_comparison" in CASE_STUDY_REGISTRY
    entry = CASE_STUDY_REGISTRY["norfolk_ssfha_comparison"]
    assert "hydroshare_resource_id_fn" in entry
    assert "config_template" in entry
    assert entry["config_template"] == "norfolk_default.yaml"


def test_template_fills_and_parses(tmp_path):
    """norfolk_default.yaml fills correctly and parses as a valid SsfhaConfig.

    Uses a synthetic data_dir that does NOT need to exist — path existence
    checks are the responsibility of validation.py, not the template/loader.
    The test verifies that:
    - All {{data_dir}} placeholders are replaced without raising
    - The resulting YAML parses as a valid SsfhaConfig via load_config
    - Key fields survive the round-trip (fha_id, return_periods, ppcct)
    """
    import yaml as _yaml
    from pathlib import Path as _Path
    from ss_fha.config import load_config, SsfhaConfig

    # Write a fake system.yaml so load_config can merge it
    fake_data_dir = tmp_path / "hydroshare_data"
    fake_data_dir.mkdir()
    (fake_data_dir / "configs").mkdir()
    system_dict = {
        "study_area_id": "norfolk_va",
        "crs_epsg": 32147,
        "geospatial": {
            "watershed": str(fake_data_dir / "geospatial" / "watershed.shp"),
        },
    }
    (fake_data_dir / "system.yaml").write_text(_yaml.safe_dump(system_dict))

    cfg = load_config(
        _TEMPLATE_PATH,
        placeholders={"data_dir": str(fake_data_dir)},
    )

    assert isinstance(cfg, SsfhaConfig)
    assert cfg.fha_id == "ssfha_combined"
    assert cfg.fha_approach == "ssfha"
    assert cfg.return_periods == [1, 2, 10, 100]
    assert cfg.ppcct is not None
    assert cfg.ppcct.n_years_observed == 18
    assert cfg.toggle_ppcct is True
    assert cfg.toggle_mcds is True
    assert len(cfg.alt_fha_analyses) == 6


def test_template_raises_on_unfilled_placeholder():
    """load_config raises ConfigurationError when placeholders dict is omitted."""
    import pytest
    from ss_fha.config import load_config
    from ss_fha.exceptions import ConfigurationError

    with pytest.raises(ConfigurationError) as exc_info:
        load_config(_TEMPLATE_PATH)
    assert "placeholder" in str(exc_info.value).lower()
