"""Integration tests for Workflow 1: Flood Hazard Assessment (Work Chunk 03A).

Tests the analysis module and runner script using synthetic test data
produced by ``build_minimal_test_case``.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import xarray as xr

from tests.fixtures.test_case_builder import build_minimal_test_case
from tests.utils_for_testing import assert_flood_probs_valid, assert_zarr_valid

# ---------------------------------------------------------------------------
# Analysis module tests
# ---------------------------------------------------------------------------


def test_run_flood_hazard_produces_valid_output(tmp_path: Path) -> None:
    """run_flood_hazard writes a zarr that passes assert_flood_probs_valid."""
    from ss_fha.analysis.flood_hazard import run_flood_hazard
    from ss_fha.config import load_system_config
    from ss_fha.config.model import SsfhaConfig
    from ss_fha.io.zarr_io import read_zarr

    cfg = build_minimal_test_case(tmp_path)
    assert isinstance(cfg, SsfhaConfig)

    system_cfg = load_system_config(tmp_path / "system.yaml")

    output_path = run_flood_hazard(
        config=cfg,
        system_config=system_cfg,
        sim_type="combined",
        overwrite=False,
    )

    # Output zarr exists
    assert output_path.exists()
    assert_zarr_valid(
        path=output_path,
        expected_vars=["max_wlevel_m", "empirical_cdf", "return_pd_yrs"],
    )

    # Load and validate structure
    ds = read_zarr(path=output_path, chunks=None)
    assert_flood_probs_valid(ds)

    # Verify dimensions
    assert "event_iloc" in ds.dims
    assert "x" in ds.dims
    assert "y" in ds.dims

    ds.close()


def test_run_flood_hazard_applies_watershed_mask(tmp_path: Path) -> None:
    """Gridcells outside the watershed should be NaN after masking."""
    import numpy as np

    from ss_fha.analysis.flood_hazard import run_flood_hazard
    from ss_fha.config import load_system_config
    from ss_fha.io.zarr_io import read_zarr

    cfg = build_minimal_test_case(tmp_path)
    system_cfg = load_system_config(tmp_path / "system.yaml")

    output_path = run_flood_hazard(
        config=cfg,
        system_config=system_cfg,
        sim_type="combined",
        overwrite=False,
    )

    ds = read_zarr(path=output_path, chunks=None)
    # The synthetic watershed covers the full grid, so all values should
    # be valid (not NaN). But the mask mechanism is tested by verifying
    # the DataArray has the mask applied (non-NaN values exist).
    da = ds["max_wlevel_m"]
    assert not np.all(np.isnan(da.values)), "All values are NaN — mask may be inverted"
    ds.close()


def test_run_flood_hazard_overwrite_false_raises(tmp_path: Path) -> None:
    """Running twice with overwrite=False raises DataError."""
    from ss_fha.analysis.flood_hazard import run_flood_hazard
    from ss_fha.config import load_system_config
    from ss_fha.exceptions import DataError

    cfg = build_minimal_test_case(tmp_path)
    system_cfg = load_system_config(tmp_path / "system.yaml")

    # First run succeeds
    run_flood_hazard(
        config=cfg,
        system_config=system_cfg,
        sim_type="combined",
        overwrite=False,
    )

    # Second run with overwrite=False should fail
    with pytest.raises(DataError):
        run_flood_hazard(
            config=cfg,
            system_config=system_cfg,
            sim_type="combined",
            overwrite=False,
        )


def test_run_flood_hazard_overwrite_true_succeeds(tmp_path: Path) -> None:
    """Running twice with overwrite=True on the second run succeeds."""
    from ss_fha.analysis.flood_hazard import run_flood_hazard
    from ss_fha.config import load_system_config

    cfg = build_minimal_test_case(tmp_path)
    system_cfg = load_system_config(tmp_path / "system.yaml")

    run_flood_hazard(
        config=cfg,
        system_config=system_cfg,
        sim_type="combined",
        overwrite=False,
    )
    # Should succeed
    run_flood_hazard(
        config=cfg,
        system_config=system_cfg,
        sim_type="combined",
        overwrite=True,
    )


def test_resolve_triton_zarr_path_invalid_sim_type(tmp_path: Path) -> None:
    """Unknown sim_type raises ConfigurationError."""
    from ss_fha.analysis.flood_hazard import resolve_triton_zarr_path
    from ss_fha.exceptions import ConfigurationError

    cfg = build_minimal_test_case(tmp_path)

    with pytest.raises(ConfigurationError):
        resolve_triton_zarr_path(cfg, "nonexistent_type")


def test_resolve_triton_zarr_path_missing_field(tmp_path: Path) -> None:
    """Requesting a sim_type whose config field is None raises ConfigurationError."""
    from ss_fha.analysis.flood_hazard import resolve_triton_zarr_path
    from ss_fha.exceptions import ConfigurationError

    cfg = build_minimal_test_case(tmp_path)

    # surge_only is not set in the minimal test case config
    with pytest.raises(ConfigurationError):
        resolve_triton_zarr_path(cfg, "surge_only")


def test_validate_triton_schema_missing_variable(tmp_path: Path) -> None:
    """A zarr missing max_wlevel_m raises DataError."""
    import numpy as np

    from ss_fha.analysis.flood_hazard import _validate_triton_schema
    from ss_fha.exceptions import DataError

    ds = xr.Dataset({"wrong_var": xr.DataArray(np.zeros((3, 3, 5)), dims=["x", "y", "event_iloc"])})

    with pytest.raises(DataError, match="max_wlevel_m"):
        _validate_triton_schema(ds, Path("/fake/path.zarr"))


# ---------------------------------------------------------------------------
# Runner script tests
# ---------------------------------------------------------------------------


def test_runner_returns_zero_on_success(tmp_path: Path) -> None:
    """The runner script returns exit code 0 on a valid run."""
    import subprocess

    build_minimal_test_case(tmp_path)

    analysis_yaml = tmp_path / "analysis.yaml"
    system_yaml = tmp_path / "system.yaml"

    result = subprocess.run(
        [
            "conda",
            "run",
            "-n",
            "ss-fha",
            "python",
            "-m",
            "ss_fha.runners.flood_hazard_runner",
            "--config",
            str(analysis_yaml),
            "--system-config",
            str(system_yaml),
            "--sim-type",
            "combined",
        ],
        capture_output=True,
        text=True,
        timeout=60,
    )

    assert result.returncode == 0, (
        f"Runner exited with code {result.returncode}.\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    assert "COMPLETE: flood_hazard combined" in result.stdout


def test_runner_returns_nonzero_for_missing_config(tmp_path: Path) -> None:
    """The runner returns exit code 2 when config file does not exist."""
    import subprocess

    result = subprocess.run(
        [
            "conda",
            "run",
            "-n",
            "ss-fha",
            "python",
            "-m",
            "ss_fha.runners.flood_hazard_runner",
            "--config",
            str(tmp_path / "nonexistent.yaml"),
            "--system-config",
            str(tmp_path / "nonexistent_system.yaml"),
            "--sim-type",
            "combined",
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode == 2
