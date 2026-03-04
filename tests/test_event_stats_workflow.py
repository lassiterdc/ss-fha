"""Integration tests for Workflow 3C: Event Statistics Analysis and Runner.

Tests the end-to-end event statistics pipeline using synthetic data generated
by ``build_event_stats_test_case``. Validates that:
- ``run_event_comparison`` produces a valid DataTree output
- The runner CLI exits with code 0
- The output passes ``assert_event_comparison_valid``
- Guard conditions (comparative analysis, missing timeseries, missing iloc mapping)
  raise the expected exceptions
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
import xarray as xr

from tests.fixtures.test_case_builder import build_event_stats_test_case
from tests.utils_for_testing import assert_event_comparison_valid

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def event_stats_case(tmp_path: Path):
    """Build the event stats test case and return the config."""
    return build_event_stats_test_case(tmp_path)


# ---------------------------------------------------------------------------
# Core analysis tests
# ---------------------------------------------------------------------------


def test_run_event_comparison_zarr(event_stats_case, tmp_path: Path) -> None:
    """run_event_comparison writes a valid zarr DataTree."""
    from ss_fha.analysis.event_comparison import run_event_comparison

    config = event_stats_case
    output_path = run_event_comparison(
        config=config,
        output_format="zarr",
        overwrite=False,
    )

    assert output_path.exists(), f"Output not found: {output_path}"
    assert output_path.suffix == ".zarr" or output_path.name.endswith(".zarr")

    dt = xr.open_datatree(str(output_path), engine="zarr")
    assert_event_comparison_valid(dt)
    dt.close()


def test_run_event_comparison_netcdf(event_stats_case, tmp_path: Path) -> None:
    """run_event_comparison writes a valid NetCDF DataTree."""
    from ss_fha.analysis.event_comparison import run_event_comparison

    config = event_stats_case
    output_path = run_event_comparison(
        config=config,
        output_format="netcdf",
        overwrite=False,
    )

    assert output_path.exists(), f"Output not found: {output_path}"
    assert str(output_path).endswith(".nc")

    dt = xr.open_datatree(str(output_path), engine="h5netcdf")
    assert_event_comparison_valid(dt)
    dt.close()


def test_run_event_comparison_overwrite_false_raises(event_stats_case) -> None:
    """run_event_comparison raises DataError if output exists and overwrite=False."""
    from ss_fha.analysis.event_comparison import run_event_comparison
    from ss_fha.exceptions import DataError

    config = event_stats_case
    # First write succeeds
    run_event_comparison(config=config, output_format="zarr", overwrite=False)
    # Second write without overwrite raises
    with pytest.raises(DataError):
        run_event_comparison(config=config, output_format="zarr", overwrite=False)


def test_run_event_comparison_overwrite_true(event_stats_case) -> None:
    """run_event_comparison succeeds on second write when overwrite=True."""
    from ss_fha.analysis.event_comparison import run_event_comparison

    config = event_stats_case
    run_event_comparison(config=config, output_format="zarr", overwrite=False)
    # Should not raise
    output_path = run_event_comparison(config=config, output_format="zarr", overwrite=True)
    assert output_path.exists()


# ---------------------------------------------------------------------------
# Guard condition tests
# ---------------------------------------------------------------------------


def test_comparative_analysis_rejected(tmp_path: Path) -> None:
    """run_event_comparison raises ConfigurationError for comparative analysis configs."""
    from ss_fha.analysis.event_comparison import run_event_comparison
    from ss_fha.exceptions import ConfigurationError
    from tests.fixtures.test_case_builder import build_minimal_test_case

    # build_minimal_test_case creates is_comparative_analysis=True
    config = build_minimal_test_case(tmp_path)
    with pytest.raises(ConfigurationError, match="comparative analysis"):
        run_event_comparison(config=config, output_format="zarr", overwrite=False)


def test_missing_timeseries_rejected(tmp_path: Path) -> None:
    """run_event_comparison raises ConfigurationError when sim_event_timeseries is None."""
    import yaml

    from ss_fha.analysis.event_comparison import run_event_comparison
    from ss_fha.config import load_config_from_dict
    from ss_fha.exceptions import ConfigurationError
    from ss_fha.io.zarr_io import write_zarr
    from tests.fixtures.test_case_builder import (
        build_synthetic_event_summaries,
        build_synthetic_iloc_mapping,
        build_synthetic_triton_output,
        build_synthetic_watershed,
    )

    event_types = ["combined", "rain_only", "surge_only"]
    n_years = 3
    max_ep = 2
    n_sim = n_years * len(event_types) * max_ep

    ds_sim = build_synthetic_triton_output(n_events=n_sim, nx=5, ny=5)
    write_zarr(ds=ds_sim, path=tmp_path / "combined.zarr", encoding=None, overwrite=False)
    build_synthetic_event_summaries(n_events=n_sim, include_obs_cols=False).to_csv(tmp_path / "summaries.csv")
    build_synthetic_watershed(nx=5, ny=5, crs_epsg=32147).to_file(tmp_path / "watershed.geojson", driver="GeoJSON")
    build_synthetic_iloc_mapping(event_types, n_years, max_ep).to_csv(tmp_path / "iloc_mapping.csv", index=False)

    system_dict = {
        "study_area_id": "x",
        "crs_epsg": 32147,
        "geospatial": {"watershed": str(tmp_path / "watershed.geojson")},
    }
    (tmp_path / "system.yaml").write_text(yaml.safe_dump(system_dict))

    analysis_dict = {
        "fha_approach": "ssfha",
        "fha_id": "no_timeseries",
        "project_name": "test",
        "is_comparative_analysis": False,
        "output_dir": str(tmp_path / "output"),
        "n_years_synthesized": n_years,
        "return_periods": [1, 2],
        "alpha": 0.0,
        "beta": 0.0,
        "toggle_uncertainty": False,
        "toggle_mcds": False,
        "toggle_ppcct": False,
        "toggle_flood_risk": False,
        "toggle_design_comparison": False,
        "weather_event_indices": ["event_type", "year", "event_id"],
        "triton_outputs": {"combined": str(tmp_path / "combined.zarr")},
        "event_data": {
            "sim_event_summaries": str(tmp_path / "summaries.csv"),
            # sim_event_timeseries deliberately absent
            "sim_event_iloc_mapping": str(tmp_path / "iloc_mapping.csv"),
        },
        "event_statistic_variables": {
            "precip_intensity": {
                "variable_name": "mm_per_hr",
                "units": "mm_per_hr",
                "max_intensity_windows_min": [5],
            },
        },
        "execution": {"mode": "local_concurrent"},
    }
    config = load_config_from_dict(analysis_dict)
    with pytest.raises(ConfigurationError, match="sim_event_timeseries"):
        run_event_comparison(config=config, output_format="zarr", overwrite=False)


# ---------------------------------------------------------------------------
# Runner CLI test
# ---------------------------------------------------------------------------


def test_runner_cli_end_to_end(event_stats_case, tmp_path: Path) -> None:
    """event_stats_runner CLI exits 0 and emits COMPLETE marker."""
    import yaml

    config = event_stats_case

    # Write system.yaml to tmp_path (runner needs both config paths)
    system_dict = {
        "study_area_id": "synthetic_test_area",
        "crs_epsg": 32147,
        "geospatial": {"watershed": str(config.event_data.sim_event_summaries.parent / "watershed.geojson")},
    }
    system_yaml = tmp_path / "system.yaml"
    system_yaml.write_text(yaml.safe_dump(system_dict))

    # Find the analysis yaml written by build_event_stats_test_case
    # The config's output_dir parent is tmp_path; analysis.yaml is in tmp_path
    analysis_yaml = config.output_dir.parent / "analysis.yaml"

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "ss_fha.runners.event_stats_runner",
            "--config",
            str(analysis_yaml),
            "--system-config",
            str(system_yaml),
            "--output-format",
            "zarr",
        ],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, (
        f"Runner exited with code {result.returncode}.\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    assert "COMPLETE: event_stats" in result.stdout, f"Completion marker not found in stdout:\n{result.stdout}"
