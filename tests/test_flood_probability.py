"""Unit tests for ss_fha.core.flood_probability (Work Chunk 02A).

Validation strategy
-------------------
1. ``calculate_positions`` is tested against scipy's own
   ``plotting_positions`` directly (identity check) and against the
   closed-form Hazen formula to confirm correctness.
2. ``calculate_return_period`` is tested against a hand-derived example
   with known n_years and n_events.
3. ``compute_emp_cdf_and_return_pds`` is tested end-to-end with a small
   synthetic xarray DataArray; the output is compared against values
   computed by calling the lower-level functions directly.
4. Both Weibull (alpha=0, beta=0) and Cunnane (alpha=0.4, beta=0.4)
   parameter sets are exercised; the test asserts they produce *different*
   results, guarding against silent regressions where both paths return
   the same values.
"""

from __future__ import annotations

import numpy as np
import pytest
import xarray as xr
from scipy.stats.mstats import plotting_positions as scipy_plotting_positions

from ss_fha.core.flood_probability import (
    calculate_positions,
    calculate_return_period,
    compute_emp_cdf_and_return_pds,
)
from ss_fha.exceptions import SSFHAError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _hazen_formula(data: np.ndarray, alpha: float, beta: float) -> np.ndarray:
    """Reference implementation of the generalized Hazen plotting position formula.

    F_i = (rank_i - alpha) / (n + 1 - alpha - beta)

    Rank is 1-indexed and assigned by sorting. Result is in original data order.
    """
    n = len(data)
    sorted_idx = np.argsort(data)
    ranks = np.empty(n)
    ranks[sorted_idx] = np.arange(1, n + 1)
    return (ranks - alpha) / (n + 1 - alpha - beta)


# ---------------------------------------------------------------------------
# calculate_positions
# ---------------------------------------------------------------------------

class TestCalculatePositions:

    def test_matches_scipy_weibull(self):
        """Results must be identical to scipy's plotting_positions (Weibull)."""
        rng = np.random.default_rng(0)
        data = rng.exponential(scale=10.0, size=50)
        result = calculate_positions(data, alpha=0.0, beta=0.0, fillna_val=np.nan)
        expected = scipy_plotting_positions(data, alpha=0.0, beta=0.0)
        np.testing.assert_allclose(result, expected, rtol=1e-10)

    def test_matches_scipy_cunnane(self):
        """Results must be identical to scipy's plotting_positions (Cunnane)."""
        rng = np.random.default_rng(1)
        data = rng.exponential(scale=10.0, size=50)
        result = calculate_positions(data, alpha=0.4, beta=0.4, fillna_val=np.nan)
        expected = scipy_plotting_positions(data, alpha=0.4, beta=0.4)
        np.testing.assert_allclose(result, expected, rtol=1e-10)

    def test_matches_hazen_formula_weibull(self):
        """Verify the underlying formula: F_i = rank / (n+1) for Weibull."""
        data = np.array([3.0, 1.0, 4.0, 1.0, 5.0, 9.0, 2.0, 6.0])
        result = calculate_positions(data, alpha=0.0, beta=0.0, fillna_val=np.nan)
        expected = _hazen_formula(data, alpha=0.0, beta=0.0)
        np.testing.assert_allclose(result, expected, rtol=1e-10)

    def test_weibull_differs_from_cunnane(self):
        """Weibull and Cunnane parameters must produce different results."""
        rng = np.random.default_rng(42)
        data = rng.exponential(scale=5.0, size=30)
        weibull = calculate_positions(data, alpha=0.0, beta=0.0, fillna_val=np.nan)
        cunnane = calculate_positions(data, alpha=0.4, beta=0.4, fillna_val=np.nan)
        assert not np.allclose(weibull, cunnane), (
            "Weibull and Cunnane should produce different plotting positions"
        )

    def test_output_in_unit_interval(self):
        """All plotting positions must be strictly in (0, 1)."""
        rng = np.random.default_rng(7)
        data = rng.exponential(scale=3.0, size=100)
        result = calculate_positions(data, alpha=0.0, beta=0.0, fillna_val=np.nan)
        assert np.all(result > 0) and np.all(result < 1)

    def test_output_shape_preserved(self):
        """Output shape matches input shape."""
        data = np.array([5.0, 2.0, 8.0, 1.0])
        result = calculate_positions(data, alpha=0.0, beta=0.0, fillna_val=np.nan)
        assert result.shape == data.shape

    def test_fillna_no_nans_in_output(self):
        """NaN values are filled with fillna_val; output must contain no NaNs."""
        data = np.array([1.0, 2.0, np.nan, 4.0])
        result = calculate_positions(data, alpha=0.0, beta=0.0, fillna_val=0.0)
        assert not np.isnan(result).any()

    def test_fillna_with_two_nans_assigned_same_position(self):
        """Multiple NaN slots filled with the same fillna_val tie for the same rank.

        When fillna_val=0.0 is used for two NaN entries and 0.0 is lower than
        all real values, both NaN slots receive the same (minimum) plotting
        position. The code then overwrites both with the max of their group,
        which is that same minimum position — so they end up equal to each other.
        """
        # Two NaNs filled with 0.0 → they tie at the lowest rank.
        data = np.array([np.nan, 3.0, np.nan, 5.0])
        result = calculate_positions(data, alpha=0.0, beta=0.0, fillna_val=0.0)
        assert not np.isnan(result).any()
        # Both NaN-origin positions must be equal (tied rank → same max-of-group value)
        assert result[0] == result[2]

    def test_nan_without_fillna_raises(self):
        """NaN data with fillna_val=np.nan must raise SSFHAError."""
        data = np.array([1.0, np.nan, 3.0])
        with pytest.raises(SSFHAError, match="NaN"):
            calculate_positions(data, alpha=0.0, beta=0.0, fillna_val=np.nan)

    def test_does_not_mutate_input(self):
        """Input array must not be modified."""
        data = np.array([1.0, np.nan, 3.0])
        original = data.copy()
        try:
            calculate_positions(data, alpha=0.0, beta=0.0, fillna_val=0.0)
        except SSFHAError:
            pass
        np.testing.assert_array_equal(data, original)


# ---------------------------------------------------------------------------
# calculate_return_period
# ---------------------------------------------------------------------------

class TestCalculateReturnPeriod:

    def test_hand_derived_example(self):
        """Verify against a fully hand-calculated example.

        Setup: 1000 synthetic years, 800 events (0.8 events/year).
        Event at plotting position F=0.8:
            exceedance = 0.2
            T = 1 / (0.2 * 0.8) = 6.25 years
        """
        positions = np.array([0.8])
        result = calculate_return_period(positions, n_years=1000, n_events=800)
        np.testing.assert_allclose(result, [6.25], rtol=1e-10)

    def test_high_cdf_value_gives_long_return_period(self):
        """Higher plotting positions (rare events) must produce longer return periods."""
        positions = np.array([0.5, 0.9, 0.99])
        result = calculate_return_period(positions, n_years=1000, n_events=1000)
        # T = 1 / ((1 - F) * 1.0) = 1 / (1 - F)
        expected = 1.0 / (1 - positions)
        np.testing.assert_allclose(result, expected, rtol=1e-10)
        assert result[0] < result[1] < result[2]

    def test_clipping_prevents_inf(self):
        """Plotting positions of exactly 0 or 1 must not produce inf or zero."""
        positions = np.array([0.0, 1.0])
        result = calculate_return_period(positions, n_years=100, n_events=100)
        assert np.all(np.isfinite(result))
        assert np.all(result > 0)

    def test_output_shape_preserved(self):
        """Output shape matches input shape."""
        positions = np.linspace(0.1, 0.9, 20)
        result = calculate_return_period(positions, n_years=500, n_events=400)
        assert result.shape == positions.shape


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
