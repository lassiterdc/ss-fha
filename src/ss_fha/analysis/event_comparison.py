"""Event statistics analysis module: univariate and multivariate event return periods.

Orchestrates the computation of event return periods from weather event time series
data and writes the results to a ``DataTree`` output (zarr or NetCDF).

Output structure
----------------
The output is an ``xr.DataTree`` with two child nodes:

::

    /                    (root — global attrs: fha_id, weather_event_indices)
    ├── univariate/      (Dataset — event_iloc × stat variables)
    └── multivariate/    (Dataset — event_iloc × event_stats combinations)

Both nodes use a flat ``event_iloc`` integer dimension sourced from the iloc mapping
CSV (``config.event_data.sim_event_iloc_mapping``). Weather event indexers
(``event_type``, ``year``, ``event_id``, ...) are stored as 1D non-index coordinates
on ``event_iloc``, enabling EDA filtering without a MultiIndex.

Replaces
--------
``_old_code_to_refactor/d0_computing_event_statistic_probabilities.py``

See Also
--------
``docs/planning/refactors/2026-02-25_full_codebase_refactor/work_chunks/03C_event_statistics_runner.md``
"""

from __future__ import annotations

import logging
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr

from ss_fha.core.event_statistics import (
    compute_all_multivariate_return_period_combinations,
    compute_univariate_event_return_periods,
)
from ss_fha.exceptions import ConfigurationError, DataError
from ss_fha.io.netcdf_io import read_netcdf
from ss_fha.paths import ProjectPaths

logger = logging.getLogger(__name__)

# Column name used in the real sim iloc mapping (legacy name for event_iloc).
_SIM_ILOC_LEGACY_COL = "event_number"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _load_iloc_mapping(path: Path) -> pd.DataFrame:
    """Load and normalise the iloc mapping CSV.

    Renames ``event_number`` → ``event_iloc`` if present (real sim mapping uses
    the legacy column name). Validates that ``event_iloc``, ``year``,
    ``event_type``, and ``event_id`` are all present.

    Parameters
    ----------
    path:
        Path to the iloc mapping CSV.

    Returns
    -------
    pd.DataFrame
        DataFrame with at minimum columns ``event_iloc``, ``year``,
        ``event_type``, ``event_id``.

    Raises
    ------
    DataError
        If the file cannot be read or required columns are missing.
    """
    try:
        df = pd.read_csv(path)
    except Exception as e:
        raise DataError(
            operation="load iloc mapping",
            filepath=path,
            reason=str(e),
        ) from e

    # Rename legacy column name used by the real sim mapping CSV.
    if _SIM_ILOC_LEGACY_COL in df.columns and "event_iloc" not in df.columns:
        df = df.rename(columns={_SIM_ILOC_LEGACY_COL: "event_iloc"})

    required = {"event_iloc", "year", "event_type", "event_id"}
    missing = required - set(df.columns)
    if missing:
        raise DataError(
            operation="load iloc mapping",
            filepath=path,
            reason=(f"Missing required columns: {sorted(missing)}. Present columns: {sorted(df.columns)}"),
        )

    return df


def _join_iloc_to_event_stats(
    df_stats: pd.DataFrame,
    df_mapping: pd.DataFrame,
    mapping_path: Path,
) -> pd.DataFrame:
    """Merge event_iloc values onto an event statistics DataFrame.

    Joins on the full event identity tuple ``(event_type, year, event_id)``
    present in both the stats DataFrame index and the iloc mapping.

    Parameters
    ----------
    df_stats:
        DataFrame with a MultiIndex of ``(event_type, year, event_id)``.
    df_mapping:
        iloc mapping DataFrame with columns ``event_iloc``, ``event_type``,
        ``year``, ``event_id``.
    mapping_path:
        Path to the mapping file (for error messages).

    Returns
    -------
    pd.DataFrame
        ``df_stats`` with an ``event_iloc`` column added, sorted by
        ``event_iloc`` ascending.

    Raises
    ------
    DataError
        If any event in ``df_stats`` has no corresponding row in ``df_mapping``.
    """
    join_cols = ["event_type", "year", "event_id"]
    df_reset = df_stats.reset_index()

    # Merge on the full identity tuple
    df_merged = df_reset.merge(
        df_mapping[["event_iloc"] + join_cols],
        on=join_cols,
        how="left",
        validate="many_to_one",
    )

    unmatched = df_merged["event_iloc"].isna()
    if unmatched.any():
        n_unmatched = int(unmatched.sum())
        sample = df_merged.loc[unmatched, join_cols].head(5).to_dict("records")
        raise DataError(
            operation="join event_iloc to event stats",
            filepath=mapping_path,
            reason=(
                f"{n_unmatched} event(s) have no matching row in the iloc mapping. Sample unmatched events: {sample}"
            ),
        )

    df_merged["event_iloc"] = df_merged["event_iloc"].astype(np.int64)
    return df_merged.sort_values("event_iloc").reset_index(drop=True)


def _build_univariate_dataset(
    df_merged: pd.DataFrame,
    weather_event_indices: list[str],
) -> xr.Dataset:
    """Construct the univariate node Dataset from a merged stats DataFrame.

    ``df_merged`` must have an ``event_iloc`` column and all
    ``weather_event_indices`` columns, plus all the stat/cdf/rp columns from
    ``compute_univariate_event_return_periods``.

    Parameters
    ----------
    df_merged:
        DataFrame with ``event_iloc``, weather indexer columns, and stat columns.
    weather_event_indices:
        Names of the weather event indexer columns.

    Returns
    -------
    xr.Dataset
        Univariate node Dataset indexed by flat ``event_iloc``.
    """
    event_iloc_arr = df_merged["event_iloc"].to_numpy(dtype=np.int64)

    # Stat/cdf/rp columns: everything except event_iloc and weather indexers
    non_stat_cols = set(weather_event_indices) | {"event_iloc"}
    stat_cols = [c for c in df_merged.columns if c not in non_stat_cols]

    data_vars: dict = {}
    for col in stat_cols:
        data_vars[col] = ("event_iloc", df_merged[col].to_numpy(dtype=np.float64))

    coords: dict = {
        "event_iloc": ("event_iloc", event_iloc_arr),
    }
    for idx_name in weather_event_indices:
        arr = df_merged[idx_name].to_numpy()
        coords[idx_name] = ("event_iloc", arr)

    ds = xr.Dataset(data_vars, coords=coords)
    ds.attrs["weather_event_indices"] = list(weather_event_indices)

    # Apply vlen string encoding to string coordinates for zarr v3
    for name in weather_event_indices:
        if ds[name].dtype.kind in ("U", "O", "S"):
            ds[name].encoding["dtype"] = str

    return ds


def _build_multivariate_dataset(
    df_multivar: pd.DataFrame,
    df_mapping: pd.DataFrame,
    weather_event_indices: list[str],
    mapping_path: Path,
) -> xr.Dataset:
    """Construct the multivariate node Dataset.

    ``df_multivar`` has a MultiIndex of ``(event_stats, *weather_event_indices)``
    and columns for the four AND/OR CDF/return-period values.

    Parameters
    ----------
    df_multivar:
        Output of ``compute_all_multivariate_return_period_combinations``.
    df_mapping:
        iloc mapping DataFrame.
    weather_event_indices:
        Names of the weather event indexer columns.
    mapping_path:
        Path to the mapping file (for error messages).

    Returns
    -------
    xr.Dataset
        Multivariate node Dataset indexed by ``event_iloc`` × ``event_stats``.
    """
    # Unstack event_stats from the MultiIndex into a column
    df_reset = df_multivar.reset_index()
    combo_labels = sorted(df_reset["event_stats"].unique())

    # Merge event_iloc for each event
    join_cols = ["event_type", "year", "event_id"]
    df_reset = df_reset.merge(
        df_mapping[["event_iloc"] + join_cols],
        on=join_cols,
        how="left",
        validate="many_to_one",
    )

    unmatched = df_reset["event_iloc"].isna()
    if unmatched.any():
        n_unmatched = int(unmatched.sum())
        sample = df_reset.loc[unmatched, join_cols].head(5).to_dict("records")
        raise DataError(
            operation="join event_iloc to multivariate stats",
            filepath=mapping_path,
            reason=(f"{n_unmatched} multivariate event(s) have no matching iloc. Sample: {sample}"),
        )
    df_reset["event_iloc"] = df_reset["event_iloc"].astype(np.int64)

    # Pivot to (event_iloc, event_stats) layout
    result_cols = [
        "empirical_multivar_cdf_AND",
        "empirical_multivar_cdf_OR",
        "empirical_multivar_rtrn_yrs_AND",
        "empirical_multivar_rtrn_yrs_OR",
    ]
    event_iloc_values = sorted(df_reset["event_iloc"].unique())
    n_events = len(event_iloc_values)
    n_combos = len(combo_labels)

    iloc_to_idx = {v: i for i, v in enumerate(event_iloc_values)}
    combo_to_idx = {v: i for i, v in enumerate(combo_labels)}

    arrays: dict[str, np.ndarray] = {
        col: np.full((n_events, n_combos), np.nan, dtype=np.float64) for col in result_cols
    }
    for _, row in df_reset.iterrows():
        ei = iloc_to_idx[int(row["event_iloc"])]
        ci = combo_to_idx[row["event_stats"]]
        for col in result_cols:
            arrays[col][ei, ci] = float(row[col])

    # Build weather indexer coordinate arrays (one value per event_iloc)
    # Use the first occurrence of each event_iloc in df_reset for indexer values
    df_iloc_meta = (
        df_reset[["event_iloc"] + join_cols]
        .drop_duplicates("event_iloc")
        .sort_values("event_iloc")
        .reset_index(drop=True)
    )

    # Build event_stats_vars companion coordinate: shape (n_combos, max_components)
    # Parse comma-separated labels to fill a 2D object array
    max_components = max(len(lbl.split(",")) for lbl in combo_labels)
    combo_components = np.full((n_combos, max_components), "", dtype=object)
    for ci, lbl in enumerate(combo_labels):
        parts = lbl.split(",")
        for pi, part in enumerate(parts):
            combo_components[ci, pi] = part.strip()
    component_slot_names = [f"var_{i}" for i in range(max_components)]

    data_vars: dict = {col: (["event_iloc", "event_stats"], arrays[col]) for col in result_cols}

    coords: dict = {
        "event_iloc": ("event_iloc", np.array(event_iloc_values, dtype=np.int64)),
        "event_stats": ("event_stats", np.array(combo_labels, dtype=object)),
        "event_stats_vars": (
            ["event_stats", "component_slot"],
            combo_components,
        ),
        "component_slot": ("component_slot", component_slot_names),
    }
    for idx_name in weather_event_indices:
        arr = df_iloc_meta[idx_name].to_numpy() if idx_name in df_iloc_meta.columns else None
        if arr is not None:
            coords[idx_name] = ("event_iloc", arr)

    ds = xr.Dataset(data_vars, coords=coords)
    ds.attrs["weather_event_indices"] = list(weather_event_indices)

    # Apply vlen string encoding to string coordinates for zarr v3
    for name in weather_event_indices:
        if name in ds.coords and ds[name].dtype.kind in ("U", "O", "S"):
            ds[name].encoding["dtype"] = str
    ds["event_stats"].encoding["dtype"] = str
    ds["event_stats_vars"].encoding["dtype"] = str

    return ds


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def run_event_comparison(
    config,
    output_format: str,
    overwrite: bool,
) -> Path:
    """Compute univariate and multivariate event return periods and write output.

    Loads the weather event time series NetCDF and iloc mapping CSV specified
    in ``config.event_data``, calls the core event statistics functions, assembles
    a ``DataTree`` with ``/univariate`` and ``/multivariate`` child nodes, and
    writes it to zarr or NetCDF.

    Parameters
    ----------
    config:
        Fully loaded ``SsfhaConfig`` (not a comparative analysis).
    output_format:
        ``"zarr"`` or ``"netcdf"``.
    overwrite:
        If ``False``, raise ``DataError`` if the output already exists.

    Returns
    -------
    Path
        Path to the written output file (zarr directory or ``.nc`` file).

    Raises
    ------
    ConfigurationError
        If ``config.is_comparative_analysis`` is True, or if required
        ``event_data`` fields are absent.
    DataError
        If any event has no iloc mapping entry, or if the output already exists
        and ``overwrite=False``.
    """
    from ss_fha.config.model import SsfhaConfig

    if not isinstance(config, SsfhaConfig):
        raise ConfigurationError(
            field="fha_approach",
            message="event_stats_runner requires fha_approach='ssfha'.",
        )
    if config.is_comparative_analysis:
        raise ConfigurationError(
            field="is_comparative_analysis",
            message=(
                "Event statistics belong to the primary analysis only. "
                "Cannot run event_comparison on a comparative analysis config."
            ),
        )
    if config.event_data.sim_event_timeseries is None:
        raise ConfigurationError(
            field="event_data.sim_event_timeseries",
            message="sim_event_timeseries is required for event statistics computation.",
        )
    if config.event_data.sim_event_iloc_mapping is None:
        raise ConfigurationError(
            field="event_data.sim_event_iloc_mapping",
            message=(
                "sim_event_iloc_mapping is required — event_iloc must always be "
                "sourced from the iloc mapping CSV, never assigned positionally."
            ),
        )
    if output_format not in ("zarr", "netcdf"):
        raise ConfigurationError(
            field="output_format",
            message=f"output_format must be 'zarr' or 'netcdf', got {output_format!r}.",
        )

    paths = ProjectPaths.from_config(config)
    paths.ensure_dirs_exist()

    suffix = ".zarr" if output_format == "zarr" else ".nc"
    output_path = paths.event_stats_dir / f"event_comparison{suffix}"

    if output_path.exists() and not overwrite:
        raise DataError(
            operation="write event comparison output",
            filepath=output_path,
            reason=("Output already exists. Pass --overwrite to replace it."),
        )

    # --- Log key parameters ---
    logger.info("n_years_synthesized = %d (from config)", config.n_years_synthesized)
    logger.info("weather_event_indices = %s", config.weather_event_indices)
    logger.info("Loading time series: %s", config.event_data.sim_event_timeseries)
    logger.info("Loading iloc mapping: %s", config.event_data.sim_event_iloc_mapping)

    # --- Load inputs ---
    ds_tseries = read_netcdf(config.event_data.sim_event_timeseries)
    df_mapping = _load_iloc_mapping(config.event_data.sim_event_iloc_mapping)

    ev_vars = config.event_statistic_variables
    assert ev_vars is not None  # validated above: non-comparative requires this field

    precip_varname: str = ev_vars.precip_intensity.variable_name
    stage_varname: str | None = ev_vars.boundary_stage.variable_name if ev_vars.boundary_stage is not None else None
    rain_windows_min: list[int] = ev_vars.precip_intensity.max_intensity_windows_min or []

    weather_event_indices: list[str] = list(config.weather_event_indices or [])

    # --- Validate required variables exist in the time series ---
    missing_vars = []
    if precip_varname not in ds_tseries.data_vars:
        missing_vars.append(precip_varname)
    if stage_varname is not None and stage_varname not in ds_tseries.data_vars:
        missing_vars.append(stage_varname)
    if missing_vars:
        raise DataError(
            operation="validate time series variables",
            filepath=config.event_data.sim_event_timeseries,
            reason=f"Required variables not found: {missing_vars}. Present: {list(ds_tseries.data_vars)}",
        )

    # --- Compute univariate return periods ---
    logger.info("Computing univariate event return periods...")
    df_rain_return_pds, df_stage_return_pds = compute_univariate_event_return_periods(
        ds_sim_tseries=ds_tseries,
        weather_event_indices=weather_event_indices,
        precip_varname=precip_varname,
        stage_varname=stage_varname,
        rain_windows_min=rain_windows_min,
        n_years=config.n_years_synthesized,
        alpha=config.alpha,
        beta=config.beta,
    )
    logger.info("Univariate return periods computed: %d events", len(df_rain_return_pds))

    # Combine rain and stage into one DataFrame for the univariate node
    if df_stage_return_pds is not None:
        df_univar = pd.concat([df_rain_return_pds, df_stage_return_pds], axis=1)
    else:
        df_univar = df_rain_return_pds

    # --- Join event_iloc ---
    df_univar_merged = _join_iloc_to_event_stats(df_univar, df_mapping, config.event_data.sim_event_iloc_mapping)

    # --- Compute multivariate return periods ---
    logger.info("Computing multivariate event return period combinations...")
    df_multivar = compute_all_multivariate_return_period_combinations(
        df_rain_return_pds=df_rain_return_pds,
        df_stage_return_pds=df_stage_return_pds,
        n_years=config.n_years_synthesized,
        alpha=config.alpha,
        beta=config.beta,
    )
    n_combos = df_multivar.index.get_level_values("event_stats").nunique()
    logger.info("Multivariate combinations computed: %d combinations", n_combos)

    # --- Build DataTree nodes ---
    ds_uni = _build_univariate_dataset(df_univar_merged, weather_event_indices)
    ds_multi = _build_multivariate_dataset(
        df_multivar, df_mapping, weather_event_indices, config.event_data.sim_event_iloc_mapping
    )

    dt = xr.DataTree.from_dict(
        {
            "/": xr.Dataset(),
            "univariate": ds_uni,
            "multivariate": ds_multi,
        }
    )
    dt.attrs["fha_id"] = config.fha_id
    dt.attrs["weather_event_indices"] = list(weather_event_indices)
    dt.attrs["description"] = "Event return period comparison output (univariate + multivariate)"

    # --- Write output ---
    if output_format == "zarr":
        logger.info("Writing zarr output: %s", output_path)
        mode = "w" if overwrite else "w-"
        with warnings.catch_warnings():
            # Suppress zarr v3 consolidated metadata warning (expected, harmless)
            warnings.filterwarnings(
                "ignore",
                message="Consolidated metadata is currently not part",
                category=UserWarning,
            )
            dt.to_zarr(str(output_path), mode=mode, consolidated=True)
    else:
        logger.info("Writing NetCDF output: %s", output_path)
        mode = "w"
        dt.to_netcdf(str(output_path), mode=mode, engine="h5netcdf")

    logger.info("Event comparison output written to: %s", output_path)
    return output_path
