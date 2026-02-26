"""Synthetic data generators for ss-fha tests.

All builder functions are pure — they return in-memory objects or write to a
caller-supplied ``tmp_path``. No argument has a default value: callers must be
explicit about every dimension and parameter.

Real data schema (verified 2026-02-26 against HydroShare model_results/):
  TRITON zarr (sim and obs):
    coords : x (float64), y (float64), event_iloc (int64)
    data   : max_wlevel_m (float64, dims=(x, y, event_iloc))
  Event summaries CSV (sim):
    index  : event_type (str), year (int), event_id (str)
    cols   : precip_depth_mm (float)
  Event summaries CSV (obs):
    index  : event_type (str), year (int), event_id (str)
    cols   : precip_depth_mm (float), event_start (str/datetime)
"""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import xarray as xr
from shapely.geometry import box

from ss_fha.config import load_config_from_dict, load_system_config
from ss_fha.config.model import SSFHAConfig
from ss_fha.io.zarr_io import write_zarr


def build_synthetic_triton_output(n_events: int, nx: int, ny: int) -> xr.Dataset:
    """Build a small xarray Dataset matching the real TRITON zarr output schema.

    Schema (verified against HydroShare model_results/ss_tritonswmm_combined.zarr):
    - Coords: x (float64), y (float64), event_iloc (int64)
    - Data var: max_wlevel_m (float64, dims=(x, y, event_iloc))

    Parameters
    ----------
    n_events:
        Number of simulated events (event_iloc dimension size).
    nx:
        Number of grid cells in the x direction.
    ny:
        Number of grid cells in the y direction.

    Returns
    -------
    xr.Dataset
        In-memory dataset structurally identical to real TRITON output.
    """
    rng = np.random.default_rng(seed=0)

    x_coords = np.linspace(364000.0, 364000.0 + 100.0 * nx, nx, dtype=np.float64)
    y_coords = np.linspace(4091000.0, 4091000.0 + 100.0 * ny, ny, dtype=np.float64)
    event_iloc_coords = np.arange(n_events, dtype=np.int64)

    # Real data: max_wlevel_m has dims (x, y, event_iloc)
    data = rng.uniform(0.0, 3.0, size=(nx, ny, n_events)).astype(np.float64)

    return xr.Dataset(
        {
            "max_wlevel_m": xr.DataArray(
                data,
                dims=["x", "y", "event_iloc"],
                coords={
                    "x": x_coords,
                    "y": y_coords,
                    "event_iloc": event_iloc_coords,
                },
            )
        }
    )


def build_synthetic_observed_output(n_events: int, nx: int, ny: int) -> xr.Dataset:
    """Build a small xarray Dataset matching the real observed TRITON zarr schema.

    Identical structure to ``build_synthetic_triton_output`` — the observed
    zarr uses the same schema as the simulated zarr, differing only in
    event_iloc count (real data: 71 observed vs 3798 simulated).

    Parameters
    ----------
    n_events:
        Number of observed events (event_iloc dimension size).
    nx:
        Number of grid cells in the x direction.
    ny:
        Number of grid cells in the y direction.

    Returns
    -------
    xr.Dataset
        In-memory dataset structurally identical to real observed TRITON output.
    """
    rng = np.random.default_rng(seed=1)

    x_coords = np.linspace(364000.0, 364000.0 + 100.0 * nx, nx, dtype=np.float64)
    y_coords = np.linspace(4091000.0, 4091000.0 + 100.0 * ny, ny, dtype=np.float64)
    event_iloc_coords = np.arange(n_events, dtype=np.int64)

    data = rng.uniform(0.0, 2.5, size=(nx, ny, n_events)).astype(np.float64)

    return xr.Dataset(
        {
            "max_wlevel_m": xr.DataArray(
                data,
                dims=["x", "y", "event_iloc"],
                coords={
                    "x": x_coords,
                    "y": y_coords,
                    "event_iloc": event_iloc_coords,
                },
            )
        }
    )


def build_synthetic_event_summaries(n_events: int, include_obs_cols: bool) -> pd.DataFrame:
    """Build a synthetic event summaries DataFrame matching the real CSV schema.

    Only the columns actually used in the ss-fha pipeline are generated
    (verified against _old_code_to_refactor/, 2026-02-26):
      - Index : event_type, year, event_id  (how the real CSVs are loaded)
      - Data  : precip_depth_mm             (used by all summary validation)
      - Data  : event_start                 (obs only; used for time-series alignment)

    Parameters
    ----------
    n_events:
        Number of events (rows) to generate.
    include_obs_cols:
        If True, include the ``event_start`` column (observed-event variant).
        If False, produce the simulated-event variant (no ``event_start``).

    Returns
    -------
    pd.DataFrame
        DataFrame with a MultiIndex of (event_type, year, event_id) and the
        relevant data columns.
    """
    rng = np.random.default_rng(seed=2)

    event_types = ["combined", "rain_only", "surge_only"]
    years = np.arange(2000, 2000 + n_events, dtype=int)
    event_ids = [f"evt_{i:03d}" for i in range(n_events)]

    # Cycle event_types across events for variety
    assigned_types = [event_types[i % len(event_types)] for i in range(n_events)]

    data: dict = {
        "event_type": assigned_types,
        "year": years,
        "event_id": event_ids,
        "precip_depth_mm": rng.uniform(10.0, 150.0, size=n_events),
    }

    if include_obs_cols:
        starts = pd.date_range("2000-09-01", periods=n_events, freq="365D")
        data["event_start"] = starts.strftime("%Y-%m-%d %H:%M:%S")

    df = pd.DataFrame(data)
    df = df.set_index(["event_type", "year", "event_id"])
    return df


def build_synthetic_watershed(nx: int, ny: int, crs_epsg: int) -> gpd.GeoDataFrame:
    """Build a synthetic watershed GeoDataFrame covering the synthetic grid.

    The bounding box exactly covers the x/y coordinates that
    ``build_synthetic_triton_output`` and ``build_synthetic_observed_output``
    generate, so that masking operations work correctly.

    Parameters
    ----------
    nx:
        Number of grid cells in the x direction (must match triton output).
    ny:
        Number of grid cells in the y direction (must match triton output).
    crs_epsg:
        EPSG code for the coordinate reference system (e.g. 32147 for Norfolk).

    Returns
    -------
    gpd.GeoDataFrame
        Single-row GeoDataFrame with a polygon covering the synthetic grid,
        in the specified CRS.
    """
    # Mirror the coordinate generation in build_synthetic_triton_output
    x_min = 364000.0
    x_max = 364000.0 + 100.0 * nx
    y_min = 4091000.0
    y_max = 4091000.0 + 100.0 * ny

    polygon = box(x_min, y_min, x_max, y_max)
    return gpd.GeoDataFrame({"geometry": [polygon]}, crs=f"EPSG:{crs_epsg}")


def build_minimal_test_case(tmp_path: Path) -> SSFHAConfig:
    """Create all synthetic data files on disk and return a valid SSFHAConfig.

    This is the primary fixture for integration tests. It writes:
    - ``combined.zarr``        — synthetic TRITON sim output
    - ``summaries.csv``        — synthetic sim event summaries
    - ``system.yaml``          — minimal SystemConfig YAML
    - ``watershed.geojson``    — synthetic watershed polygon
    - ``analysis.yaml``        — SsfhaConfig YAML pointing at the above files

    All synthetic data uses: 10 events, 10×10 grid, EPSG:32147.

    Parameters
    ----------
    tmp_path:
        Temporary directory (e.g. pytest's ``tmp_path`` fixture) in which all
        files are written. The caller controls lifecycle — nothing persists.

    Returns
    -------
    SSFHAConfig
        Fully valid, file-backed SsfhaConfig ready for integration tests.
    """
    n_sim_events = 10
    nx = 10
    ny = 10
    crs_epsg = 32147

    # --- Write combined TRITON zarr ---
    ds_sim = build_synthetic_triton_output(n_events=n_sim_events, nx=nx, ny=ny)
    combined_zarr = tmp_path / "combined.zarr"
    write_zarr(ds=ds_sim, path=combined_zarr, encoding=None, overwrite=False)

    # --- Write sim event summaries CSV ---
    df_sim = build_synthetic_event_summaries(n_events=n_sim_events, include_obs_cols=False)
    summaries_csv = tmp_path / "summaries.csv"
    df_sim.to_csv(summaries_csv)

    # --- Write synthetic watershed as GeoJSON ---
    gdf = build_synthetic_watershed(nx=nx, ny=ny, crs_epsg=crs_epsg)
    watershed_path = tmp_path / "watershed.geojson"
    gdf.to_file(watershed_path, driver="GeoJSON")

    # --- Write system.yaml ---
    import yaml

    system_dict = {
        "study_area_id": "synthetic_test_area",
        "crs_epsg": crs_epsg,
        "geospatial": {
            "watershed": str(watershed_path),
        },
    }
    system_yaml = tmp_path / "system.yaml"
    system_yaml.write_text(yaml.safe_dump(system_dict, sort_keys=False))

    # --- Write analysis.yaml ---
    analysis_dict = {
        "fha_approach": "ssfha",
        "fha_id": "synthetic_ssfha",
        "project_name": "synthetic_test",
        "output_dir": str(tmp_path / "output"),
        "n_years_synthesized": 100,
        "return_periods": [1, 2, 10, 100],
        "toggle_uncertainty": False,
        "toggle_mcds": False,
        "toggle_ppcct": False,
        "toggle_flood_risk": False,
        "toggle_design_comparison": False,
        "triton_outputs": {"combined": str(combined_zarr)},
        "event_data": {"sim_event_summaries": str(summaries_csv)},
        "execution": {"mode": "local_concurrent"},
    }
    analysis_yaml = tmp_path / "analysis.yaml"
    analysis_yaml.write_text(yaml.safe_dump(analysis_dict, sort_keys=False))

    return load_config_from_dict(analysis_dict)
