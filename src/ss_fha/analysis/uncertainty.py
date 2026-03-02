"""Workflow 2: Flood Hazard Uncertainty (Bootstrap Confidence Intervals).

Orchestrates bootstrap CI computation from Workflow 1 flood probability outputs.
This module is the bridge between I/O and the pure computation in
``ss_fha.core.bootstrapping``. It contains no computation of its own.

Steps (bootstrap_runner.py, one invocation per sample):
    1. Load Workflow 1 flood probability zarr (max_wlevel_m, pre-masked)
    2. Load event iloc mapping CSV
    3. Draw bootstrap years (seeded from base_seed + sample_id)
    4. Assemble resampled flood depth DataArray
    5. Compute return-period-indexed depths
    6. Write per-sample zarr to bootstrap_samples_dir

Steps (bootstrap_combine_runner.py, once after all samples complete):
    1. Verify all expected sample zarrs are present
    2. Open all sample zarrs lazily via xr.open_mfdataset + Dask
    3. Compute 0.05 / 0.50 / 0.95 quantiles across the sample dimension
    4. Check for NA values — fail fast if any are found
    5. Write combined CI zarr to bootstrap_dir

Replaces: _old_code_to_refactor/c1_fpm_confidence_intervals_bootstrapping.py
          _old_code_to_refactor/c1b_fpm_confidence_intervals_bootstrapping.py
"""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr

from ss_fha.config.model import SsfhaConfig
from ss_fha.core.bootstrapping import (
    assemble_bootstrap_sample,
    compute_return_period_indexed_depths,
    draw_bootstrap_years,
)
from ss_fha.exceptions import ConfigurationError, DataError
from ss_fha.io.zarr_io import read_zarr, write_zarr
from ss_fha.paths import ProjectPaths

logger = logging.getLogger(__name__)


def prepare_bootstrap_run(config: SsfhaConfig, paths: ProjectPaths) -> None:
    """Validate inputs for a bootstrap run and create required directories.

    Call this once before launching bootstrap_runner.py fan-out jobs. It
    validates that Workflow 1 outputs and the iloc mapping CSV exist, and
    that ``uncertainty`` config is present.

    Parameters
    ----------
    config:
        Loaded SsfhaConfig with ``toggle_uncertainty=True``.
    paths:
        ProjectPaths derived from ``config``.

    Raises
    ------
    ConfigurationError
        If ``toggle_uncertainty=False`` or ``uncertainty`` config section is
        missing.
    DataError
        If the Workflow 1 flood probability zarr for ``combined`` sim type
        does not exist, or if ``sim_event_iloc_mapping`` is not set on
        ``event_data``.
    """
    if not config.toggle_uncertainty:
        raise ConfigurationError(
            field="toggle_uncertainty",
            message="prepare_bootstrap_run called but toggle_uncertainty=False.",
        )
    if config.uncertainty is None:
        raise ConfigurationError(
            field="uncertainty",
            message="toggle_uncertainty=True but 'uncertainty' config section is missing.",
        )
    if config.event_data.sim_event_iloc_mapping is None:
        raise ConfigurationError(
            field="event_data.sim_event_iloc_mapping",
            message=(
                "toggle_uncertainty=True but 'event_data.sim_event_iloc_mapping' is not set. "
                "This CSV maps each simulated event to its year and event_iloc index."
            ),
        )

    # Verify Workflow 1 combined output exists (bootstrap requires it)
    flood_probs_zarr = paths.flood_probs_dir / "combined.zarr"
    if not flood_probs_zarr.exists():
        raise DataError(
            operation="prepare_bootstrap_run",
            filepath=flood_probs_zarr,
            reason=(
                "Workflow 1 flood probability zarr not found. "
                "Run flood_hazard_runner.py --sim-type combined before bootstrap."
            ),
        )

    iloc_mapping_path = Path(config.event_data.sim_event_iloc_mapping)
    if not iloc_mapping_path.exists():
        raise DataError(
            operation="prepare_bootstrap_run",
            filepath=iloc_mapping_path,
            reason="Event iloc mapping CSV not found.",
        )

    paths.ensure_dirs_exist()
    logger.info(
        "Bootstrap run prepared: %d samples, base_seed=%d",
        config.uncertainty.n_bootstrap_samples,
        config.uncertainty.bootstrap_base_seed,
    )


def run_bootstrap_sample(
    config: SsfhaConfig,
    paths: ProjectPaths,
    sim_type: str,
    sample_id: int,
    overwrite: bool,
) -> Path:
    """Compute return-period-indexed flood depths for one bootstrap sample.

    This function is designed to be called by ``bootstrap_runner.py`` — one
    invocation per ``sample_id``, fully independent with no shared state.

    Parameters
    ----------
    config:
        Loaded SsfhaConfig.
    paths:
        ProjectPaths derived from ``config``.
    sim_type:
        Simulation type to bootstrap (e.g. ``"combined"``). Must correspond
        to an existing Workflow 1 output zarr at
        ``paths.flood_probs_dir / f"{sim_type}.zarr"``.
    sample_id:
        Zero-based bootstrap sample index. Determines the RNG seed via
        ``base_seed + sample_id``.
    overwrite:
        If ``True``, overwrite an existing sample zarr. If ``False`` and the
        output already exists, raise ``DataError``.

    Returns
    -------
    Path
        Path to the written per-sample zarr store.

    Raises
    ------
    ConfigurationError
        If ``uncertainty`` config section is missing.
    DataError
        If the flood probability zarr or iloc mapping CSV does not exist.
    """
    if config.uncertainty is None:
        raise ConfigurationError(
            field="uncertainty",
            message="run_bootstrap_sample requires 'uncertainty' config section.",
        )

    # --- Load Workflow 1 output ---
    flood_probs_path = paths.flood_probs_dir / f"{sim_type}.zarr"
    if not flood_probs_path.exists():
        raise DataError(
            operation="run_bootstrap_sample",
            filepath=flood_probs_path,
            reason=(
                f"Workflow 1 flood probability zarr not found for sim_type='{sim_type}'. "
                "Run flood_hazard_runner.py first."
            ),
        )
    logger.info("Loading flood probability zarr: %s", flood_probs_path)
    ds_flood_probs = read_zarr(path=flood_probs_path, chunks="auto")
    da_flood_probs = ds_flood_probs["max_wlevel_m"]

    # --- Load event iloc mapping ---
    if config.event_data.sim_event_iloc_mapping is None:
        raise ConfigurationError(
            field="event_data.sim_event_iloc_mapping",
            message="run_bootstrap_sample requires 'event_data.sim_event_iloc_mapping'.",
        )
    iloc_mapping_path = Path(config.event_data.sim_event_iloc_mapping)
    logger.info("Loading event iloc mapping: %s", iloc_mapping_path)
    event_iloc_mapping = pd.read_csv(iloc_mapping_path)

    # years_with_events: unique years present in the mapping (event-free years absent)
    years_with_events = event_iloc_mapping["year"].unique()

    # --- Draw bootstrap years ---
    resampled_years = draw_bootstrap_years(
        n_years_synthesized=config.n_years_synthesized,
        base_seed=config.uncertainty.bootstrap_base_seed,
        sample_id=sample_id,
    )
    logger.info(
        "Drew %d resampled years (sample_id=%d, seed=%d)",
        len(resampled_years),
        sample_id,
        config.uncertainty.bootstrap_base_seed + sample_id,
    )

    # --- Assemble bootstrap sample ---
    da_sample = assemble_bootstrap_sample(
        resampled_years=resampled_years,
        years_with_events=years_with_events,
        event_iloc_mapping=event_iloc_mapping,
        da_flood_probs=da_flood_probs,
    )

    if da_sample.sizes["event_iloc"] == 0:
        raise DataError(
            operation="run_bootstrap_sample",
            filepath=flood_probs_path,
            reason=(
                f"Bootstrap sample {sample_id} has zero events after resampling. "
                "All resampled years were event-free. This is statistically very "
                "unlikely for typical ensemble sizes — check n_years_synthesized "
                f"({config.n_years_synthesized}) and the iloc mapping."
            ),
        )

    # Materialise the assembled sample before sorting. apply_ufunc requires
    # core dimensions to be unchunked; computing here avoids rechunking overhead
    # and keeps per-sample memory bounded (n_events × nx × ny floats).
    logger.info("Materialising assembled bootstrap sample (sample_id=%d)...", sample_id)
    da_sample = da_sample.compute()

    # --- Compute return-period-indexed depths ---
    da_return_pd = compute_return_period_indexed_depths(
        da_stacked=da_sample,
        alpha=config.alpha,
        beta=config.beta,
        n_years=config.n_years_synthesized,
    )

    # --- Write output ---
    output_path = paths.bootstrap_samples_dir / f"{sim_type}_{sample_id:04d}.zarr"
    ds_out = da_return_pd.to_dataset(name="max_wlevel_m")
    write_zarr(ds=ds_out, path=output_path, encoding=None, overwrite=overwrite)
    logger.info("Wrote bootstrap sample zarr: %s", output_path)

    return output_path


def combine_and_quantile(
    config: SsfhaConfig,
    paths: ProjectPaths,
    sim_type: str,
    overwrite: bool,
) -> Path:
    """Combine all bootstrap sample zarrs and compute quantile CIs.

    Reads all per-sample zarrs produced by ``run_bootstrap_sample``, combines
    them lazily using Dask, computes 0.05/0.50/0.95 quantiles across the
    sample dimension, validates for NA values, and writes the combined CI zarr.

    Note on memory strategy: ``xr.open_mfdataset`` + Dask opens all sample
    zarrs lazily. Dask computes quantiles chunk-by-chunk over the spatial
    dimensions without materialising all samples at once. If this is too slow
    at full scale, fall back to a two-step approach (concatenate → write to
    disk → compute quantiles). See ``docs/planning/bugs/tech_debt_known_risks.md``.

    Parameters
    ----------
    config:
        Loaded SsfhaConfig.
    paths:
        ProjectPaths derived from ``config``.
    sim_type:
        Simulation type (e.g. ``"combined"``).
    overwrite:
        If ``True``, overwrite the existing combined CI zarr.

    Returns
    -------
    Path
        Path to the written combined CI zarr.

    Raises
    ------
    ConfigurationError
        If ``uncertainty`` config section is missing.
    DataError
        If any expected sample zarrs are missing, or if NA values are found
        in the combined output.
    """
    if config.uncertainty is None:
        raise ConfigurationError(
            field="uncertainty",
            message="combine_and_quantile requires 'uncertainty' config section.",
        )

    n_samples = config.uncertainty.n_bootstrap_samples

    # --- Verify all expected sample zarrs exist ---
    expected_paths = [paths.bootstrap_samples_dir / f"{sim_type}_{i:04d}.zarr" for i in range(n_samples)]
    missing = [str(p) for p in expected_paths if not p.exists()]
    if missing:
        raise DataError(
            operation="combine_and_quantile",
            filepath=paths.bootstrap_samples_dir,
            reason=(
                f"{len(missing)} of {n_samples} expected bootstrap sample zarrs are missing:\n"
                + "\n".join(f"  {m}" for m in missing)
            ),
        )

    logger.info(
        "Combining %d bootstrap sample zarrs for sim_type='%s'",
        n_samples,
        sim_type,
    )

    # --- Open all samples lazily with Dask ---
    # Each sample zarr has dims (x, y, return_pd_yrs) and variable max_wlevel_m.
    # open_mfdataset concatenates along a new 'sample_id' dimension.
    ds_combined = xr.open_mfdataset(
        [str(p) for p in expected_paths],
        engine="zarr",
        concat_dim="sample_id",
        combine="nested",
        join="outer",  # samples may have different return_pd_yrs lengths; outer preserves all
        chunks="auto",
    )

    # --- Compute quantiles across sample dimension ---
    bootstrap_quantiles = config.uncertainty.bootstrap_quantiles
    logger.info("Computing quantiles: %s", bootstrap_quantiles)
    da_quantiles = ds_combined["max_wlevel_m"].quantile(
        q=bootstrap_quantiles,
        dim="sample_id",
        method="closest_observation",
    )

    # Materialise before NA check and write
    logger.info("Computing results...")
    da_quantiles_computed = da_quantiles.compute()

    # --- NA validation ---
    nan_count = int(np.isnan(da_quantiles_computed.values).sum())
    if nan_count > 0:
        raise DataError(
            operation="combine_and_quantile",
            filepath=paths.bootstrap_dir,
            reason=(
                f"{nan_count} NA values found in combined bootstrap output for "
                f"sim_type='{sim_type}'. This may indicate missing or corrupt sample "
                "zarrs, or NaN values in the Workflow 1 flood probability zarr. "
                "Investigate before proceeding."
            ),
        )
    logger.info("NA check passed — no NA values in combined output.")

    # --- Write combined CI zarr ---
    ds_ci = da_quantiles_computed.to_dataset(name="max_wlevel_m")
    output_path = paths.bootstrap_dir / f"{sim_type}_ci.zarr"
    write_zarr(ds=ds_ci, path=output_path, encoding=None, overwrite=overwrite)
    logger.info("Wrote combined CI zarr: %s", output_path)

    ds_combined.close()
    return output_path
