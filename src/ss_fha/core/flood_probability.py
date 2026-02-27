"""Core flood probability computation functions.

All functions here are pure computation — no I/O, no file operations,
no side effects. They operate on already-loaded xarray objects and return
xarray objects or numpy arrays.

Plotting positions and return period conversion:
    see ``ss_fha.core.empirical_frequency_analysis``.
"""

from __future__ import annotations

import numpy as np
import xarray as xr

from ss_fha.core.empirical_frequency_analysis import (
    calculate_positions,
    calculate_return_period,
)
from ss_fha.exceptions import SSFHAError


def compute_emp_cdf_and_return_pds(
    da_wlevel: xr.DataArray,
    alpha: float,
    beta: float,
    n_years: int,
) -> xr.Dataset:
    """Compute empirical CDF and return periods across a spatial flood depth grid.

    Takes a stacked (event_iloc, x, y) DataArray of peak flood depths and
    returns a Dataset with three variables:

    - the original flood depth values (name preserved from input)
    - ``empirical_cdf`` — per-event plotting positions at each gridcell
    - ``return_pd_yrs`` — per-event return periods in years at each gridcell

    The ``event_iloc`` dimension must already be present (use
    ``stack_wlevel_dataset`` from the runner layer to create it from the
    multi-index year/event_type/event_id dimensions before calling this
    function).

    Computation is performed via ``xr.apply_ufunc`` with Dask parallelization.
    The function is vectorized over the spatial (x, y) dimensions — each
    gridcell's event vector is processed independently.

    Parameters
    ----------
    da_wlevel:
        DataArray with dimension ``event_iloc`` (and optionally ``x``, ``y``).
        Must already be stacked so that ``event_iloc`` is a flat dimension.
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
        ``event_iloc`` (and spatial dims if present).

    Notes
    -----
    NaN fill value for ``calculate_positions`` is set to 0.0, meaning gridcells
    with no flood depth (NaN) are treated as having zero depth and assigned
    the maximum computed empirical CDF value (i.e., the most common
    non-exceedance probability). This preserves the rank structure for
    flooded gridcells.
    """
    if "event_iloc" not in da_wlevel.dims:
        raise SSFHAError(
            "compute_emp_cdf_and_return_pds: 'event_iloc' dimension not found in "
            f"da_wlevel. Found dimensions: {list(da_wlevel.dims)}. "
            "Stack year/event_type/event_id into event_iloc before calling this function."
        )

    n_events = len(da_wlevel.event_iloc.values)

    # --- Empirical CDF (plotting positions) ---
    positions = xr.apply_ufunc(
        calculate_positions,
        da_wlevel,
        input_core_dims=[["event_iloc"]],
        output_core_dims=[["event_iloc"]],
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
        input_core_dims=[["event_iloc"]],
        output_core_dims=[["event_iloc"]],
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
