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
