"""Core flood probability computation functions.

All functions here are pure computation — no I/O, no file operations,
no side effects. They operate on already-loaded xarray objects and return
xarray objects or numpy arrays.

Plotting positions
------------------
``calculate_positions`` delegates to ``scipy.stats.mstats.plotting_positions``,
which implements the generalized Hazen family:

    F_i = (i - alpha) / (n + 1 - alpha - beta)

where ``i`` is the rank (1-indexed) and ``n`` is the sample size. Common
named methods and their (alpha, beta) parameters:

    Weibull       (0.0,  0.0)   — unbiased for any distribution; used in this project by default
    Hazen         (0.5,  0.5)   — midpoint of each class interval
    Cunnane       (0.4,  0.4)   — approximately unbiased for normal distribution
    Gringorten    (0.44, 0.44)  — approximately unbiased for Gumbel (EV1) distribution
    Blom          (0.375, 0.375) — approximately unbiased for normal distribution

See scipy.stats.mstats.plotting_positions documentation for full details.
"""

from __future__ import annotations

import numpy as np
import xarray as xr
from scipy.stats.mstats import plotting_positions

from ss_fha.exceptions import SSFHAError


def calculate_positions(
    data: np.ndarray,
    alpha: float,
    beta: float,
    fillna_val: float,
) -> np.ndarray:
    """Compute empirical CDF plotting positions for a 1D array.

    Uses ``scipy.stats.mstats.plotting_positions`` to compute the generalized
    Hazen-family plotting positions. See module docstring for the formula and
    named method (alpha, beta) mappings.

    NaN handling: pass ``fillna_val`` to substitute a fill value for NaNs
    before computing positions. After computation, all positions that
    correspond to originally-NaN entries are set to the maximum computed
    position in their group (i.e., NaN values are treated as if they tied
    for the highest rank). Pass ``np.nan`` as ``fillna_val`` to disable NaN
    filling — an error will be raised if any NaNs remain in the data.

    Parameters
    ----------
    data:
        1D array of values. Must not contain NaN unless ``fillna_val`` is
        provided (i.e., not ``np.nan``).
    alpha:
        Plotting position parameter. See module docstring for named methods.
    beta:
        Plotting position parameter. See module docstring for named methods.
    fillna_val:
        Value to substitute for NaNs before computing positions. Pass
        ``np.nan`` to indicate no fill (NaNs will raise an error).

    Returns
    -------
    np.ndarray
        1D array of plotting positions (empirical CDF values) in the same
        order as the input data (not sorted).

    Raises
    ------
    SSFHAError
        If any NaN values remain after applying ``fillna_val``.
    """
    data = data.copy()
    idx_null = np.isnan(data)
    na_vals_present = idx_null.sum() > 0

    if na_vals_present:
        if np.isnan(fillna_val):
            raise SSFHAError(
                f"calculate_positions: {idx_null.sum()} of {len(data)} values are NaN. "
                "Pass a numeric fillna_val to substitute NaNs before computing "
                "plotting positions."
            )
        data[idx_null] = fillna_val

    result = plotting_positions(data, alpha=alpha, beta=beta)

    if na_vals_present:
        result[idx_null] = result[idx_null].max()

    return result


def calculate_return_period(
    positions: np.ndarray,
    n_years: int,
    n_events: int,
) -> np.ndarray:
    """Convert empirical CDF plotting positions to return periods.

    Return period is defined as the average recurrence interval in years:

        T = 1 / (P_exceedance * lambda)

    where ``lambda = n_events / n_years`` is the average event rate per year
    and ``P_exceedance = 1 - F`` is the exceedance probability.

    Does not require the positions to be sorted.

    Parameters
    ----------
    positions:
        1D array of empirical CDF values (plotting positions), in [0, 1].
        Values are clipped to [1e-10, 1 - 1e-10] to avoid divide-by-zero.
    n_years:
        Number of synthetic years in the simulation ensemble.
    n_events:
        Total number of events in the sample (length of the stacked event
        dimension, after removing all-NaN events).

    Returns
    -------
    np.ndarray
        1D array of return periods in years, same order as ``positions``.
    """
    positions = positions.clip(min=1e-10, max=1 - 1e-10)
    events_per_year = n_events / n_years
    exceedance_prob = 1 - positions
    return 1 / (exceedance_prob * events_per_year)


def compute_emp_cdf_and_return_pds(
    da_wlevel: xr.DataArray,
    alpha: float,
    beta: float,
    n_years: int,
) -> xr.Dataset:
    """Compute empirical CDF and return periods across a spatial flood depth grid.

    Takes a stacked (event_number, x, y) DataArray of peak flood depths and
    returns a Dataset with three variables:

    - the original flood depth values (name preserved from input)
    - ``empirical_cdf`` — per-event plotting positions at each gridcell
    - ``return_pd_yrs`` — per-event return periods in years at each gridcell

    The ``event_number`` dimension must already be present (use
    ``stack_wlevel_dataset`` from the runner layer to create it from the
    multi-index year/event_type/event_id dimensions before calling this
    function).

    Computation is performed via ``xr.apply_ufunc`` with Dask parallelization.
    The function is vectorized over the spatial (x, y) dimensions — each
    gridcell's event vector is processed independently.

    Parameters
    ----------
    da_wlevel:
        DataArray with dimension ``event_number`` (and optionally ``x``, ``y``).
        Must already be stacked so that ``event_number`` is a flat dimension.
    alpha:
        Plotting position alpha parameter. See module docstring for named
        method (alpha, beta) mappings.
    beta:
        Plotting position beta parameter.
    n_years:
        Number of synthetic years in the simulation ensemble. Must be passed
        explicitly — do not infer from ``len(da_wlevel.year)`` (the dataset
        may have fewer years than synthesized due to missing events).

    Returns
    -------
    xr.Dataset
        Dataset with variables: the original flood depth variable,
        ``empirical_cdf``, and ``return_pd_yrs``, all indexed by
        ``event_number`` (and spatial dims if present).

    Notes
    -----
    NaN fill value for ``calculate_positions`` is set to 0.0, meaning gridcells
    with no flood depth (NaN) are treated as having zero depth and assigned
    the maximum computed empirical CDF value (i.e., the most common
    non-exceedance probability). This preserves the rank structure for
    flooded gridcells.
    """
    if "event_number" not in da_wlevel.dims:
        raise SSFHAError(
            "compute_emp_cdf_and_return_pds: 'event_number' dimension not found in "
            f"da_wlevel. Found dimensions: {list(da_wlevel.dims)}. "
            "Stack year/event_type/event_id into event_number before calling this function."
        )

    n_events = len(da_wlevel.event_number.values)

    # --- Empirical CDF (plotting positions) ---
    positions = xr.apply_ufunc(
        calculate_positions,
        da_wlevel,
        input_core_dims=[["event_number"]],
        output_core_dims=[["event_number"]],
        vectorize=True,
        dask="parallelized",
        output_dtypes=[float],
        keep_attrs=True,
        kwargs={"alpha": alpha, "beta": beta, "fillna_val": 0.0},
    )

    # --- Return periods ---
    return_periods = xr.apply_ufunc(
        calculate_return_period,
        positions,
        input_core_dims=[["event_number"]],
        output_core_dims=[["event_number"]],
        vectorize=True,
        dask="parallelized",
        output_dtypes=[float],
        kwargs={"n_years": n_years, "n_events": n_events},
    )

    da_emp_cdf = positions.copy()
    da_emp_cdf.name = "empirical_cdf"

    da_return_pds = return_periods.copy()
    da_return_pds.name = "return_pd_yrs"

    return xr.merge([da_wlevel, da_emp_cdf, da_return_pds])
