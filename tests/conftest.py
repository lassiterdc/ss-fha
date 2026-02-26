"""Shared pytest fixtures for ss-fha tests.

All fixtures that write files use ``tmp_path`` (function-scoped by default),
so every test run starts from fresh synthetic data. Nothing is persisted to
disk between runs — this guarantees fixtures stay in sync with any future
changes to the synthetic data schema.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import xarray as xr

from tests.fixtures.test_case_builder import (
    build_minimal_test_case,
    build_synthetic_event_summaries,
    build_synthetic_observed_output,
    build_synthetic_triton_output,
    build_synthetic_watershed,
)


@pytest.fixture
def tmp_project_dir(tmp_path: Path) -> Path:
    """Temporary directory with the expected ss-fha project structure.

    Creates subdirectories mirroring a real project layout:
      tmp_path/
        cases/
        output/
        logs/

    Returns the root ``tmp_path``.
    """
    (tmp_path / "cases").mkdir()
    (tmp_path / "output").mkdir()
    (tmp_path / "logs").mkdir()
    return tmp_path


@pytest.fixture
def minimal_config(tmp_path: Path):
    """Smallest valid SSFHAConfig (Workflow 1 only, all toggles off).

    Calls ``build_minimal_test_case`` which writes all required files to
    ``tmp_path`` and returns a file-backed ``SSFHAConfig``. The returned
    config passes ``preflight_validate`` without errors.
    """
    return build_minimal_test_case(tmp_path)


@pytest.fixture
def full_config(tmp_path: Path):
    """SSFHAConfig with all optional workflows enabled.

    Extends the minimal case with:
    - ``toggle_ppcct=True``  (requires observed zarr + obs summaries CSV)
    - ``toggle_uncertainty=True``

    All referenced files are written to ``tmp_path``.
    """
    import yaml

    from ss_fha.config import load_config_from_dict
    from ss_fha.io.zarr_io import write_zarr

    n_sim_events = 10
    n_obs_events = 5
    nx = 10
    ny = 10
    crs_epsg = 32147

    # --- Sim zarr ---
    ds_sim = build_synthetic_triton_output(n_events=n_sim_events, nx=nx, ny=ny)
    combined_zarr = tmp_path / "combined.zarr"
    write_zarr(ds=ds_sim, path=combined_zarr, encoding=None, overwrite=False)

    # --- Observed zarr ---
    ds_obs = build_synthetic_observed_output(n_events=n_obs_events, nx=nx, ny=ny)
    observed_zarr = tmp_path / "observed.zarr"
    write_zarr(ds=ds_obs, path=observed_zarr, encoding=None, overwrite=False)

    # --- Sim event summaries ---
    df_sim = build_synthetic_event_summaries(n_events=n_sim_events, include_obs_cols=False)
    sim_summaries_csv = tmp_path / "sim_summaries.csv"
    df_sim.to_csv(sim_summaries_csv)

    # --- Obs event summaries ---
    df_obs = build_synthetic_event_summaries(n_events=n_obs_events, include_obs_cols=True)
    obs_summaries_csv = tmp_path / "obs_summaries.csv"
    df_obs.to_csv(obs_summaries_csv)

    # --- Watershed ---
    import geopandas as gpd  # noqa: F401 — ensure available

    gdf = build_synthetic_watershed(nx=nx, ny=ny, crs_epsg=crs_epsg)
    watershed_path = tmp_path / "watershed.geojson"
    gdf.to_file(watershed_path, driver="GeoJSON")

    analysis_dict = {
        "fha_approach": "ssfha",
        "fha_id": "synthetic_full_ssfha",
        "project_name": "synthetic_test_full",
        "output_dir": str(tmp_path / "output"),
        "n_years_synthesized": 100,
        "return_periods": [1, 2, 10, 100],
        "toggle_uncertainty": True,
        "toggle_mcds": False,
        "toggle_ppcct": True,
        "toggle_flood_risk": False,
        "toggle_design_comparison": False,
        "triton_outputs": {
            "combined": str(combined_zarr),
            "observed": str(observed_zarr),
        },
        "event_data": {
            "sim_event_summaries": str(sim_summaries_csv),
            "obs_event_summaries": str(obs_summaries_csv),
        },
        "ppcct": {"n_years_observed": 18},
        "execution": {"mode": "local_concurrent"},
    }

    return load_config_from_dict(analysis_dict)


@pytest.fixture
def synthetic_flood_dataset() -> xr.Dataset:
    """Small xarray Dataset mimicking TRITON zarr output (in-memory).

    Uses the standard synthetic dimensions: 10 events, 10×10 grid.
    Suitable for unit tests that need a realistic Dataset without touching disk.
    """
    return build_synthetic_triton_output(n_events=10, nx=10, ny=10)
