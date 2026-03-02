"""Workflow 1: Flood Hazard Assessment.

Orchestrates flood probability computation from TRITON model outputs.
This module is the bridge between I/O (zarr_io, gis_io) and pure
computation (flood_probability). It contains no computation of its own.

Steps:
    1. Load TRITON zarr (peak flood depths per gridcell per event)
    2. Apply watershed mask (NaN outside the study area boundary)
    3. Compute empirical CDF and return periods via flood_probability
    4. Write output zarr to flood_probs_dir/{sim_type}.zarr

Replaces: _old_code_to_refactor/b1_analyze_triton_outputs_fld_prob_calcs.py
"""

from __future__ import annotations

import logging
from pathlib import Path

import xarray as xr

from ss_fha.config.model import SsfhaConfig, SystemConfig
from ss_fha.core.flood_probability import compute_emp_cdf_and_return_pds
from ss_fha.exceptions import ConfigurationError, DataError
from ss_fha.io.gis_io import create_mask_from_polygon
from ss_fha.io.zarr_io import read_zarr, write_zarr
from ss_fha.paths import ProjectPaths

logger = logging.getLogger(__name__)

# Valid --sim-type CLI values mapped to TritonOutputsConfig field names.
# The config model stores each sim type's zarr path as a field on
# TritonOutputsConfig; this mapping resolves CLI strings to field names.
SIM_TYPE_FIELD_MAP: dict[str, str] = {
    "combined": "combined",
    "surge_only": "surge_only",
    "rain_only": "rain_only",
    "triton_only_combined": "triton_only_combined",
}


def resolve_triton_zarr_path(config: SsfhaConfig, sim_type: str) -> Path:
    """Resolve the TRITON zarr path for a given simulation type.

    Parameters
    ----------
    config:
        Loaded SsfhaConfig instance.
    sim_type:
        One of the valid simulation type strings (``combined``,
        ``surge_only``, ``rain_only``, ``triton_only_combined``).

    Returns
    -------
    Path
        Absolute path to the TRITON zarr store for the requested sim type.

    Raises
    ------
    ConfigurationError
        If ``sim_type`` is not a valid simulation type or if the config
        does not contain a zarr path for it.
    """
    if sim_type not in SIM_TYPE_FIELD_MAP:
        raise ConfigurationError(
            field="sim_type",
            message=(f"Unknown simulation type '{sim_type}'. Valid types: {sorted(SIM_TYPE_FIELD_MAP.keys())}"),
        )

    field_name = SIM_TYPE_FIELD_MAP[sim_type]
    zarr_path = getattr(config.triton_outputs, field_name, None)

    if zarr_path is None:
        raise ConfigurationError(
            field=f"triton_outputs.{field_name}",
            message=(
                f"No zarr path configured for simulation type '{sim_type}'. "
                f"Add 'triton_outputs.{field_name}' to the analysis YAML."
            ),
        )

    return Path(zarr_path)


def _validate_triton_schema(ds: xr.Dataset, zarr_path: Path) -> xr.DataArray:
    """Validate TRITON zarr schema and return the flood depth DataArray.

    Parameters
    ----------
    ds:
        Loaded TRITON xarray Dataset.
    zarr_path:
        Path to the zarr store (for error messages).

    Returns
    -------
    xr.DataArray
        The ``max_wlevel_m`` DataArray.

    Raises
    ------
    DataError
        If ``max_wlevel_m`` is missing or expected dimensions are absent.
    """
    if "max_wlevel_m" not in ds.data_vars:
        raise DataError(
            operation="validate TRITON zarr schema",
            filepath=zarr_path,
            reason=(f"Expected variable 'max_wlevel_m' not found. Present variables: {list(ds.data_vars)}"),
        )

    da = ds["max_wlevel_m"]
    required_dims = {"event_iloc", "x", "y"}
    missing_dims = required_dims - set(da.dims)
    if missing_dims:
        raise DataError(
            operation="validate TRITON zarr schema",
            filepath=zarr_path,
            reason=(
                f"Expected dimensions {sorted(required_dims)} but "
                f"missing: {sorted(missing_dims)}. "
                f"Found dimensions: {list(da.dims)}"
            ),
        )

    return da


def run_flood_hazard(
    config: SsfhaConfig,
    system_config: SystemConfig,
    sim_type: str,
    overwrite: bool,
) -> Path:
    """Run the flood hazard assessment workflow for one simulation type.

    Parameters
    ----------
    config:
        Loaded SsfhaConfig instance.
    system_config:
        Loaded SystemConfig instance (provides CRS and watershed path).
    sim_type:
        Simulation type to process (``combined``, ``surge_only``,
        ``rain_only``, ``triton_only_combined``).
    overwrite:
        If ``True``, overwrite existing output zarr. If ``False`` and
        the output already exists, raise ``DataError``.

    Returns
    -------
    Path
        Path to the written flood probability zarr store.
    """
    paths = ProjectPaths.from_config(config)
    paths.ensure_dirs_exist()

    # --- Resolve input path ---
    zarr_path = resolve_triton_zarr_path(config, sim_type)
    logger.info("Loading TRITON zarr: %s", zarr_path)

    # --- Load TRITON zarr ---
    ds = read_zarr(path=zarr_path, chunks="auto")
    da_wlevel = _validate_triton_schema(ds, zarr_path)

    # --- Apply watershed mask ---
    logger.info("Applying watershed mask from: %s", system_config.geospatial.watershed)
    mask = create_mask_from_polygon(
        polygon=system_config.geospatial.watershed,
        reference_ds=ds,
        crs_epsg=system_config.crs_epsg,
    )
    da_wlevel = da_wlevel.where(mask)

    # --- Compute empirical CDF and return periods ---
    logger.info(
        "Computing flood probabilities (alpha=%.2f, beta=%.2f, n_years=%d)",
        config.alpha,
        config.beta,
        config.n_years_synthesized,
    )
    ds_flood_probs = compute_emp_cdf_and_return_pds(
        da_wlevel=da_wlevel,
        alpha=config.alpha,
        beta=config.beta,
        n_years=config.n_years_synthesized,
    )

    # --- QAQC plots ---
    # Implemented in work chunk 05
    # (docs/planning/refactors/2026-02-25_full_codebase_refactor/work_chunks/05_visualization.md)

    # --- Compute and write output ---
    # Compute before writing to avoid zarr V3 codec issues with dask masked arrays.
    # MEMORY WARNING: At full scale (~3700 events x 550x550 grid), this materializes
    # ~25 GB into RAM. Must be profiled during Phase 6 case study validation.
    # See full_codebase_refactor.md "Risks and Edge Cases" for mitigation options.
    logger.info("Computing results...")
    ds_flood_probs = ds_flood_probs.compute()

    output_path = paths.flood_probs_dir / f"{sim_type}.zarr"
    logger.info("Writing flood probability zarr: %s", output_path)
    write_zarr(
        ds=ds_flood_probs,
        path=output_path,
        encoding=None,
        overwrite=overwrite,
    )

    return output_path
