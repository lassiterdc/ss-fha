"""Tests for ss_fha.config and ss_fha.exceptions (Work Chunk 01A)."""

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
