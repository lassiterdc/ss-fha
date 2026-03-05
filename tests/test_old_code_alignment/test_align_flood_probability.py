"""Old-code alignment tests for 02A — flood probability.

Tests verify that the refactored ``compute_emp_cdf_and_return_pds`` in
``ss_fha.core.flood_probability`` produces numerically identical results
to the old implementation in ``_old_code_to_refactor/__utils.py``.

Key differences handled:
- Dimension name: old uses ``event_number``, new uses ``event_iloc``
- Variable name typo: old names CDF ``emprical_cdf``, new uses ``empirical_cdf``
- fillna_val: old does not pass fillna_val to calculate_positions; new passes 0.0.
  Both are identical for non-NaN inputs (which is all we test here).
- n_years: old defaults to len(da_wlevel.year); new requires explicit. Always explicit here.
- Lazy vs eager: old calls .copy().load(); new returns lazy. Compare after .compute().
"""

from __future__ import annotations

import numpy as np
import pytest
import xarray as xr

# Old code imports — conftest.py handles sys.path and __inputs mocking
from __utils import compute_emp_cdf_and_return_pds as _old_compute
from __utils import stack_wlevel_dataset as _old_stack_wlevel_dataset

# New code imports
from ss_fha.core.empirical_frequency_analysis import calculate_positions
from ss_fha.core.flood_probability import compute_emp_cdf_and_return_pds as _new_compute
from ss_fha.exceptions import SSFHAError


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
def _make_synthetic_da(
    n_x: int,
    n_y: int,
    n_events: int,
    *,
    seed: int = 42,
    dim_name: str = "event_number",
    var_name: str = "max_wlevel_m",
) -> xr.DataArray:
    """Create a synthetic flood-depth DataArray with no NaN values."""
    rng = np.random.default_rng(seed)
    data = rng.exponential(scale=0.5, size=(n_x, n_y, n_events)).astype(np.float64)
    return xr.DataArray(
        data,
        dims=["x", "y", dim_name],
        coords={
            "x": np.arange(n_x, dtype=float),
            "y": np.arange(n_y, dtype=float),
            dim_name: np.arange(n_events),
        },
        name=var_name,
    )


def _make_unstacked_da(
    n_x: int,
    n_y: int,
    n_years: int,
    n_event_types: int,
    n_event_ids: int,
    *,
    seed: int = 42,
    var_name: str = "max_wlevel_m",
) -> xr.DataArray:
    """Create a synthetic DataArray with (x, y, year, event_type, event_id) dims."""
    rng = np.random.default_rng(seed)
    shape = (n_x, n_y, n_years, n_event_types, n_event_ids)
    data = rng.exponential(scale=0.5, size=shape).astype(np.float64)
    years = np.arange(2000, 2000 + n_years)
    event_types = [f"type_{i}" for i in range(n_event_types)]
    event_ids = np.arange(n_event_ids)
    return xr.DataArray(
        data,
        dims=["x", "y", "year", "event_type", "event_id"],
        coords={
            "x": np.arange(n_x, dtype=float),
            "y": np.arange(n_y, dtype=float),
            "year": years,
            "event_type": event_types,
            "event_id": event_ids,
        },
        name=var_name,
    )


# ---------------------------------------------------------------------------
# Alignment tests: compute_emp_cdf_and_return_pds
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "alpha, beta, n_years",
    [
        (0.0, 0.0, 100),  # Weibull
        (0.5, 0.5, 100),  # Hazen
        (0.4, 0.4, 50),   # Cunnane with different n_years
        (0.0, 0.0, 1000), # Weibull with large n_years
    ],
    ids=["weibull_100yr", "hazen_100yr", "cunnane_50yr", "weibull_1000yr"],
)
def test_compute_emp_cdf_and_return_pds_alignment(alpha, beta, n_years):
    """Old and new compute_emp_cdf_and_return_pds produce identical values."""
    n_x, n_y, n_events = 3, 4, 20

    # Old function: uses "event_number" dimension
    da_old = _make_synthetic_da(n_x, n_y, n_events, dim_name="event_number")
    ds_old = _old_compute(
        da_old,
        alpha=alpha,
        beta=beta,
        qaqc_plots=False,
        export_intermediate_outputs=False,
        dir_temp_zarrs=None,
        f_out_zarr=None,
        testing=False,
        print_benchmarking=False,
        n_years=n_years,
        f_event_number_mapping=None,
    )

    # New function: uses "event_iloc" dimension
    da_new = _make_synthetic_da(n_x, n_y, n_events, dim_name="event_iloc")
    ds_new = _new_compute(da_new, alpha=alpha, beta=beta, n_years=n_years)
    ds_new = ds_new.compute()

    # Compare empirical CDF values (old: "emprical_cdf", new: "empirical_cdf")
    old_cdf = ds_old["emprical_cdf"].values
    new_cdf = ds_new["empirical_cdf"].values
    np.testing.assert_allclose(old_cdf, new_cdf, rtol=1e-12, atol=0)

    # Compare return period values
    old_rp = ds_old["return_pd_yrs"].values
    new_rp = ds_new["return_pd_yrs"].values
    np.testing.assert_allclose(old_rp, new_rp, rtol=1e-12, atol=0)

    # Compare flood depth values (should be unchanged passthrough)
    old_wl = ds_old["max_wlevel_m"].values
    new_wl = ds_new["max_wlevel_m"].values
    np.testing.assert_allclose(old_wl, new_wl, rtol=1e-15, atol=0)


# ---------------------------------------------------------------------------
# Alignment test: stack_wlevel_dataset
# ---------------------------------------------------------------------------
def test_stack_wlevel_dataset_alignment():
    """Old stack_wlevel_dataset produces same stacked values as manual stacking.

    The new code does not have a separate stack function — stacking is done
    in the runner layer before calling compute_emp_cdf_and_return_pds. This
    test verifies that the old stacking logic (stack → dropna → reset_index)
    produces a result that, when passed to the old compute function, gives
    the same answer as the new compute function given equivalently pre-stacked
    input.
    """
    n_x, n_y, n_years, n_event_types, n_event_ids = 2, 3, 5, 2, 3
    alpha, beta = 0.0, 0.0

    # Create unstacked data for old function
    da_unstacked = _make_unstacked_da(
        n_x, n_y, n_years, n_event_types, n_event_ids
    )

    # Old path: stack_wlevel_dataset then compute
    stacked_old = _old_stack_wlevel_dataset(
        da_unstacked,
        f_zar_out=None,
        export_to_file=False,
        f_csv_mapping=None,
    )
    n_events_old = len(stacked_old.event_number)
    ds_old = _old_compute(
        stacked_old,
        alpha=alpha,
        beta=beta,
        qaqc_plots=False,
        export_intermediate_outputs=False,
        dir_temp_zarrs=None,
        f_out_zarr=None,
        testing=False,
        print_benchmarking=False,
        n_years=n_years,
        f_event_number_mapping=None,
    )

    # New path: manually stack (mimicking what the runner does) then compute
    da_new = da_unstacked.stack(event_iloc=["year", "event_type", "event_id"])
    da_new = da_new.dropna(dim="event_iloc", how="all").reset_index("event_iloc")
    da_new = da_new.assign_coords(event_iloc=da_new["event_iloc"])
    da_new = da_new.reset_coords(drop=True)
    # Reassign a simple integer coordinate (matching what the runner would do)
    da_new = da_new.assign_coords(event_iloc=np.arange(len(da_new.event_iloc)))

    ds_new = _new_compute(da_new, alpha=alpha, beta=beta, n_years=n_years)
    ds_new = ds_new.compute()

    # Both should have the same number of events
    assert n_events_old == len(da_new.event_iloc)

    # Compare CDF and return period values
    old_cdf = ds_old["emprical_cdf"].values
    new_cdf = ds_new["empirical_cdf"].values
    np.testing.assert_allclose(old_cdf, new_cdf, rtol=1e-12, atol=0)

    old_rp = ds_old["return_pd_yrs"].values
    new_rp = ds_new["return_pd_yrs"].values
    np.testing.assert_allclose(old_rp, new_rp, rtol=1e-12, atol=0)


# ---------------------------------------------------------------------------
# Error-path test: sys.exit() inventory Phase 2
# ---------------------------------------------------------------------------
def test_calculate_positions_raises_on_nan_without_fillna():
    """New calculate_positions raises SSFHAError for NaN input with fillna_val=np.nan.

    Verifies the error path that corresponds to the old code's sys.exit()
    at __utils.py:1567. The old code would call sys.exit() when NaN values
    are present and no fillna_val is provided. The new code raises SSFHAError.
    """
    data_with_nan = np.array([1.0, 2.0, np.nan, 4.0, 5.0])
    with pytest.raises(SSFHAError, match="NaN"):
        calculate_positions(data_with_nan, alpha=0.0, beta=0.0, fillna_val=np.nan)
