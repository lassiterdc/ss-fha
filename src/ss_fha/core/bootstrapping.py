"""Core bootstrapping computation functions for flood hazard uncertainty estimation.

Scope
-----
This module covers single-sample bootstrap computation only:

1. Draw a resampled year array for one bootstrap sample (``draw_bootstrap_years``).
2. Assemble the stacked flood depth DataArray for that sample (``assemble_bootstrap_sample``).
3. Compute return-period-indexed flood depths from the stacked sample
   (``compute_return_period_indexed_depths``).

Combining N per-sample outputs, computing quantile CIs across samples, and
post-combine QA are runner-layer responsibilities (Phase 3B).

RNG seeding strategy
--------------------
Each bootstrap sample uses ``np.random.default_rng(base_seed + sample_id)``.
This ensures:

- Any individual sample can be reproduced independently from its ``sample_id``
  alone — critical for Snakemake re-runs of failed jobs.
- Different ``base_seed`` values produce statistically independent ensembles.

``base_seed`` must be provided explicitly (also stored in ``SsfhaConfig.uncertainty``
for run-level documentation). There is no module-level default.

Year pool correctness
---------------------
Year resampling draws from ``np.arange(n_years_synthesized)`` — ALL synthetic
years, including those with no simulated events. Event-free years contribute
zero events to the bootstrap sample. Using only years-with-events as the pool
would shrink the effective denominator and systematically overstate return
periods. This is a correctness-critical distinction.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import xarray as xr

from ss_fha.core.empirical_frequency_analysis import calculate_positions, calculate_return_period
from ss_fha.exceptions import SSFHAError


def draw_bootstrap_years(
    n_years_synthesized: int,
    base_seed: int,
    sample_id: int,
) -> np.ndarray:
    """Draw a bootstrap resample of synthetic years for one sample.

    Samples ``n_years_synthesized`` years with replacement from
    ``np.arange(n_years_synthesized)`` (all synthetic years, including those
    with no simulated events). Uses a seeded RNG for reproducibility.

    Parameters
    ----------
    n_years_synthesized:
        Total number of synthetic years in the weather model run, including
        event-free years. This is the pool size AND the resample size.
        Do NOT use ``len(ds.year)`` — that excludes event-free years.
    base_seed:
        Base integer seed. The RNG is initialized with ``base_seed + sample_id``,
        making each sample independently reproducible. Must match the value
        stored in ``SsfhaConfig.uncertainty.bootstrap_base_seed``.
    sample_id:
        Zero-based index of this bootstrap sample. Added to ``base_seed``
        to produce a unique seed per sample.

    Returns
    -------
    np.ndarray
        1D integer array of length ``n_years_synthesized``. Values are year
        indices in ``[0, n_years_synthesized)``, sampled with replacement.
    """
    rng = np.random.default_rng(base_seed + sample_id)
    return rng.choice(n_years_synthesized, size=n_years_synthesized, replace=True)


def assemble_bootstrap_sample(
    resampled_years: np.ndarray,
    years_with_events: np.ndarray,
    event_iloc_mapping: pd.DataFrame,
    da_flood_probs: xr.DataArray,
) -> xr.DataArray:
    """Assemble a stacked flood depth DataArray for one bootstrap sample.

    Filters ``resampled_years`` to those present in ``years_with_events``,
    looks up the corresponding event_iloc values from ``event_iloc_mapping``,
    selects the matching flood depth slices from ``da_flood_probs``, and
    returns them concatenated with reassigned sequential event_iloc values.

    Event-free years (years in ``resampled_years`` that are not in
    ``years_with_events``) are silently skipped — they contribute zero events
    to the sample, correctly reducing the effective event rate for that draw.

    Parameters
    ----------
    resampled_years:
        1D integer array of resampled year indices (output of
        ``draw_bootstrap_years``). May contain duplicates (sampling with
        replacement).
    years_with_events:
        1D integer array of year indices that have at least one simulated
        event. Typically ``da_flood_probs.year.values`` or equivalent.
    event_iloc_mapping:
        DataFrame with at minimum a ``year`` column and an ``event_iloc``
        column, mapping each event to its flat ``event_iloc`` index in
        ``da_flood_probs``. One row per event.
    da_flood_probs:
        DataArray with an ``event_iloc`` dimension containing peak flood
        depths for all events. Must use 0.0 for dry gridcells — NaN values
        are not valid and will raise ``SSFHAError``.

    Returns
    -------
    xr.DataArray
        Stacked DataArray with the same spatial dimensions as ``da_flood_probs``
        and a new sequential ``event_iloc`` coordinate starting from 0.
        Returns an empty DataArray (zero events) if no resampled years have
        events — callers should handle this case.

    Raises
    ------
    SSFHAError
        If any NaN values are present in the assembled sample. NaN indicates
        either that the input dataset was not pre-processed to replace dry
        gridcells with 0.0, or that there is a data integrity issue upstream.
        Investigate before proceeding.
    """
    years_with_events_set = set(years_with_events.tolist())
    da_slices = []
    next_event_idx = 0

    for year in resampled_years:
        if year not in years_with_events_set:
            continue

        event_ilocs = (
            event_iloc_mapping.loc[
                event_iloc_mapping["year"] == year, "event_iloc"
            ].tolist()
        )
        if not event_ilocs:
            continue

        da_year = da_flood_probs.sel(event_iloc=event_ilocs)
        n = len(event_ilocs)
        da_year = da_year.assign_coords(
            event_iloc=np.arange(next_event_idx, next_event_idx + n)
        )
        next_event_idx += n
        da_slices.append(da_year)

    if not da_slices:
        # All resampled years were event-free — return empty DataArray
        empty_coords = {
            k: v for k, v in da_flood_probs.coords.items()
            if k != "event_iloc"
        }
        return xr.DataArray(
            np.empty(
                [da_flood_probs.sizes[d] for d in da_flood_probs.dims if d != "event_iloc"]
                + [0],
                dtype=da_flood_probs.dtype,
            ),
            dims=[d for d in da_flood_probs.dims if d != "event_iloc"] + ["event_iloc"],
            coords={**empty_coords, "event_iloc": np.array([], dtype=int)},
            name=da_flood_probs.name,
        )

    stacked = xr.concat(da_slices, dim="event_iloc")

    nan_count = int(np.isnan(stacked.values).sum())
    if nan_count > 0:
        raise SSFHAError(
            f"assemble_bootstrap_sample: {nan_count} NaN values found in the assembled "
            f"bootstrap sample. "
            "If your model outputs NaN for dry gridcells, convert to 0.0 before calling "
            "this function. If NaN values are unexpected, this may indicate missing events "
            "or corrupted input data — please investigate before proceeding."
        )

    return stacked


def sort_last_dim(arr: np.ndarray) -> np.ndarray:
    """Sort a numpy array along its last axis in ascending order.

    Used internally by ``compute_return_period_indexed_depths`` via
    ``xr.apply_ufunc`` to sort flood depths across the event dimension at
    each gridcell.

    Parameters
    ----------
    arr:
        Array of any shape. Sorting is applied along ``axis=-1``.

    Returns
    -------
    np.ndarray
        Array of the same shape as ``arr``, sorted ascending along the
        last axis.
    """
    return np.sort(arr, axis=-1)


def compute_return_period_indexed_depths(
    da_stacked: xr.DataArray,
    alpha: float,
    beta: float,
    n_years: int,
) -> xr.DataArray:
    """Compute flood depths indexed by return period for one bootstrap sample.

    Sorts flood depths at each gridcell in ascending order, computes the
    corresponding return periods from plotting positions, and returns a
    DataArray where the ``event_iloc`` dimension is replaced by
    ``return_pd_yrs``.

    The return-period-indexed form is required for the bootstrap CI step:
    to ask "what is the flood depth at the 100-year return period in sample
    k?", return period must be a coordinate axis.

    A single set of return period values is computed from one representative
    gridcell (using spatial-maximum flood depths) and applied to all gridcells.
    This is consistent with the old code approach: return period depends only
    on the plotting positions and event rate, both of which are spatially
    uniform for a given bootstrap sample.

    Parameters
    ----------
    da_stacked:
        DataArray with an ``event_iloc`` dimension. Output of
        ``assemble_bootstrap_sample``. Must contain no NaN values.
    alpha:
        Plotting position alpha parameter (passed to ``calculate_positions``).
        See ``ss_fha.core.flood_probability`` module docstring for named method
        (alpha, beta) mappings.
    beta:
        Plotting position beta parameter.
    n_years:
        Number of synthetic years in the full (un-resampled) ensemble.
        This is ``n_years_synthesized`` from config — the total year pool
        used in ``draw_bootstrap_years``.

    Returns
    -------
    xr.DataArray
        DataArray with the same spatial dimensions as ``da_stacked`` and a
        ``return_pd_yrs`` coordinate replacing ``event_iloc``. Values are
        flood depths sorted in ascending order, indexed by return period.

    Raises
    ------
    SSFHAError
        If ``da_stacked`` has no events (empty ``event_iloc`` dimension).
    """
    n_events = da_stacked.sizes["event_iloc"]

    if n_events == 0:
        raise SSFHAError(
            "compute_return_period_indexed_depths: da_stacked has zero events. "
            "This bootstrap sample drew only event-free years. "
            "Handle the empty-sample case in the caller before calling this function."
        )

    # Compute return period axis from plotting positions + event rate
    # Use a representative 1D series (spatial-max depth per event) to derive
    # the shared return period coordinate. All gridcells have the same
    # n_events and n_years, so return periods differ only by plotting position
    # rank — which is identical for all gridcells after sorting.
    representative = da_stacked.max(
        [d for d in da_stacked.dims if d != "event_iloc"]
    ).values
    positions = np.sort(
        calculate_positions(representative, alpha=alpha, beta=beta, fillna_val=0.0)
    )
    return_period_values = calculate_return_period(
        positions, n_years=n_years, n_events=n_events
    )

    # Sort flood depths along event_iloc at every gridcell
    sorted_da = xr.apply_ufunc(
        sort_last_dim,
        da_stacked,
        input_core_dims=[["event_iloc"]],
        output_core_dims=[["return_pd_yrs"]],
        dask_gufunc_kwargs={"output_sizes": {"return_pd_yrs": n_events}},
        vectorize=True,
        dask="parallelized",
        output_dtypes=[da_stacked.dtype],
    )

    # Assign the return period coordinate
    sorted_da = sorted_da.assign_coords(return_pd_yrs=return_period_values)

    return sorted_da
