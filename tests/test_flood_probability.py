"""Unit tests for ss_fha.core.flood_probability (Work Chunk 02A).

Note: ``calculate_positions`` and ``calculate_return_period`` moved to
``ss_fha.core.empirical_frequency_analysis`` (Work Chunk 02E). Their
dedicated tests are in ``tests/test_empirical_frequency_analysis.py``.
They are imported here only because ``TestComputeEmpCdfAndReturnPds``
uses them as reference values.

Validation strategy
-------------------
1. ``compute_emp_cdf_and_return_pds`` is tested end-to-end with a small
   synthetic xarray DataArray; the output is compared against values
   computed by calling the lower-level functions directly.
2. Both Weibull (alpha=0, beta=0) and Cunnane (alpha=0.4, beta=0.4)
   parameter sets are exercised; the test asserts they produce *different*
   results, guarding against silent regressions where both paths return
   the same values.
"""

from __future__ import annotations

import numpy as np
import pytest
import xarray as xr

from ss_fha.core.empirical_frequency_analysis import (
    calculate_positions,
    calculate_return_period,
)
from ss_fha.core.flood_probability import compute_emp_cdf_and_return_pds
from ss_fha.exceptions import SSFHAError


# ---------------------------------------------------------------------------
# compute_emp_cdf_and_return_pds
# ---------------------------------------------------------------------------

class TestComputeEmpCdfAndReturnPds:

    @pytest.fixture
    def simple_stacked_da(self) -> xr.DataArray:
        """Small (3x3 spatial, 20 events) DataArray already stacked on event_iloc."""
        rng = np.random.default_rng(99)
        nx, ny, n_events = 3, 3, 20
        data = rng.exponential(scale=1.0, size=(nx, ny, n_events)).astype("float32")
        return xr.DataArray(
            data,
            dims=["x", "y", "event_iloc"],
            coords={
                "x": np.arange(nx, dtype=float),
                "y": np.arange(ny, dtype=float),
                "event_iloc": np.arange(n_events),
            },
            name="flood_depth",
        )

    def test_output_has_expected_variables(self, simple_stacked_da):
        ds = compute_emp_cdf_and_return_pds(
            simple_stacked_da, alpha=0.0, beta=0.0, n_years=1000
        )
        assert "flood_depth" in ds
        assert "empirical_cdf" in ds
        assert "return_pd_yrs" in ds

    def test_output_shape_matches_input(self, simple_stacked_da):
        ds = compute_emp_cdf_and_return_pds(
            simple_stacked_da, alpha=0.0, beta=0.0, n_years=1000
        )
        assert ds["empirical_cdf"].shape == simple_stacked_da.shape
        assert ds["return_pd_yrs"].shape == simple_stacked_da.shape

    def test_empirical_cdf_in_unit_interval(self, simple_stacked_da):
        ds = compute_emp_cdf_and_return_pds(
            simple_stacked_da, alpha=0.0, beta=0.0, n_years=1000
        )
        cdf_vals = ds["empirical_cdf"].values
        assert np.all(cdf_vals > 0) and np.all(cdf_vals < 1)

    def test_return_periods_positive(self, simple_stacked_da):
        ds = compute_emp_cdf_and_return_pds(
            simple_stacked_da, alpha=0.0, beta=0.0, n_years=1000
        )
        assert np.all(ds["return_pd_yrs"].values > 0)

    def test_matches_lower_level_functions(self, simple_stacked_da):
        """End-to-end: output must match direct calls to calculate_positions/calculate_return_period."""
        alpha, beta, n_years = 0.0, 0.0, 1000
        ds = compute_emp_cdf_and_return_pds(
            simple_stacked_da, alpha=alpha, beta=beta, n_years=n_years
        )
        n_events = len(simple_stacked_da.event_iloc.values)

        # Spot-check a single gridcell (x=1, y=2)
        raw = simple_stacked_da.sel(x=1.0, y=2.0).values
        expected_cdf = calculate_positions(raw, alpha=alpha, beta=beta, fillna_val=0.0)
        expected_rp = calculate_return_period(expected_cdf, n_years=n_years, n_events=n_events)

        actual_cdf = ds["empirical_cdf"].sel(x=1.0, y=2.0).values
        actual_rp = ds["return_pd_yrs"].sel(x=1.0, y=2.0).values

        np.testing.assert_allclose(actual_cdf, expected_cdf, rtol=1e-5)
        np.testing.assert_allclose(actual_rp, expected_rp, rtol=1e-5)

    def test_weibull_differs_from_cunnane_end_to_end(self, simple_stacked_da):
        """Different alpha/beta parameters must produce different outputs."""
        ds_weibull = compute_emp_cdf_and_return_pds(
            simple_stacked_da, alpha=0.0, beta=0.0, n_years=1000
        )
        ds_cunnane = compute_emp_cdf_and_return_pds(
            simple_stacked_da, alpha=0.4, beta=0.4, n_years=1000
        )
        assert not np.allclose(
            ds_weibull["empirical_cdf"].values,
            ds_cunnane["empirical_cdf"].values,
        )

    def test_missing_event_iloc_dim_raises(self):
        """DataArray without event_iloc dimension must raise SSFHAError."""
        da = xr.DataArray(
            np.ones((3, 3)),
            dims=["x", "y"],
            name="flood_depth",
        )
        with pytest.raises(SSFHAError, match="event_iloc"):
            compute_emp_cdf_and_return_pds(da, alpha=0.0, beta=0.0, n_years=1000)

    def test_n_years_affects_return_periods(self, simple_stacked_da):
        """Doubling n_years must double all return period values."""
        ds_1000 = compute_emp_cdf_and_return_pds(
            simple_stacked_da, alpha=0.0, beta=0.0, n_years=1000
        )
        ds_2000 = compute_emp_cdf_and_return_pds(
            simple_stacked_da, alpha=0.0, beta=0.0, n_years=2000
        )
        np.testing.assert_allclose(
            ds_2000["return_pd_yrs"].values,
            ds_1000["return_pd_yrs"].values * 2,
            rtol=1e-5,
        )
