"""Unit tests for ss_fha.core.empirical_frequency_analysis (Work Chunk 02E).

Validation strategy
-------------------
1. ``calculate_positions`` is tested against scipy's own
   ``plotting_positions`` directly (identity check) and against the
   closed-form Hazen formula to confirm correctness.
2. ``calculate_return_period`` is tested against a hand-derived example
   with known n_years and n_events.
4. Both Weibull (alpha=0, beta=0) and Cunnane (alpha=0.4, beta=0.4)
   parameter sets are exercised; the test asserts they produce *different*
   results, guarding against silent regressions where both paths return
   the same values.
5. ``compute_return_periods_for_series`` is tested for structural properties
   (column names, sort order, positive return periods) and for the two
   behaviours of the ``assign_dup_vals_max_return`` flag.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from scipy.stats.mstats import plotting_positions as scipy_plotting_positions

from ss_fha.core.empirical_frequency_analysis import (
    calculate_positions,
    calculate_return_period,
    compute_return_periods_for_series,
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
# compute_return_periods_for_series
# ---------------------------------------------------------------------------

@pytest.fixture
def simple_series() -> pd.Series:
    """10-element Series of unique values with a MultiIndex."""
    rng = np.random.default_rng(123)
    values = rng.exponential(scale=5.0, size=10)
    idx = pd.MultiIndex.from_tuples(
        [(f"type_{i}", 2000 + i, 0) for i in range(10)],
        names=["event_type", "year", "event_id"],
    )
    return pd.Series(values, index=idx, name="peak_flow")


@pytest.fixture
def series_with_duplicates() -> pd.Series:
    """Series with duplicate values to test assign_dup_vals_max_return."""
    values = [1.0, 1.0, 2.0, 3.0, 3.0]
    idx = pd.MultiIndex.from_tuples(
        [(f"type_{i}", 2000 + i, 0) for i in range(5)],
        names=["event_type", "year", "event_id"],
    )
    return pd.Series(values, index=idx, name="peak_flow")


class TestComputeReturnPeriodsForSeries:

    def test_output_columns(self, simple_series):
        """Output DataFrame has expected column names."""
        df = compute_return_periods_for_series(
            simple_series, n_years=1000, alpha=0.0, beta=0.0,
            assign_dup_vals_max_return=False,
        )
        varname = str(simple_series.name)
        assert list(df.columns) == [varname, f"{varname}_emp_cdf", f"{varname}_return_pd_yrs"]

    def test_sorted_by_index(self, simple_series):
        """Output is sorted by the original index (sort_index), not by value."""
        df = compute_return_periods_for_series(
            simple_series, n_years=1000, alpha=0.0, beta=0.0,
            assign_dup_vals_max_return=False,
        )
        # The index of the output must match the sorted original index
        expected_index = simple_series.index.sort_values()
        pd.testing.assert_index_equal(df.index, expected_index)

    def test_return_period_positive(self, simple_series):
        """All return period values are positive."""
        df = compute_return_periods_for_series(
            simple_series, n_years=1000, alpha=0.0, beta=0.0,
            assign_dup_vals_max_return=False,
        )
        varname = str(simple_series.name)
        assert (df[f"{varname}_return_pd_yrs"] > 0).all()

    def test_varname_override(self, simple_series):
        """Passing an explicit varname renames the value column correctly."""
        df = compute_return_periods_for_series(
            simple_series, n_years=1000, alpha=0.0, beta=0.0,
            assign_dup_vals_max_return=False,
            varname="my_stat",
        )
        # The output column should use the *original* series name, not varname,
        # because varname is used internally for grouping, then renamed back.
        assert str(simple_series.name) in df.columns
        assert "my_stat_emp_cdf" in df.columns
        assert "my_stat_return_pd_yrs" in df.columns

    def test_assign_dup_max_return_true(self, series_with_duplicates):
        """When assign_dup_vals_max_return=True, duplicate values receive max return period."""
        df = compute_return_periods_for_series(
            series_with_duplicates, n_years=1000, alpha=0.0, beta=0.0,
            assign_dup_vals_max_return=True,
        )
        varname = str(series_with_duplicates.name)
        rp_col = f"{varname}_return_pd_yrs"
        # All rows with value=1.0 must have the same return period
        rp_for_1 = df.loc[df[varname] == 1.0, rp_col].values
        assert len(rp_for_1) == 2
        assert rp_for_1[0] == rp_for_1[1]
        # All rows with value=3.0 must have the same return period
        rp_for_3 = df.loc[df[varname] == 3.0, rp_col].values
        assert len(rp_for_3) == 2
        assert rp_for_3[0] == rp_for_3[1]

    def test_assign_dup_max_return_false(self, series_with_duplicates):
        """When assign_dup_vals_max_return=False, duplicate values get distinct CDF values."""
        df = compute_return_periods_for_series(
            series_with_duplicates, n_years=1000, alpha=0.0, beta=0.0,
            assign_dup_vals_max_return=False,
        )
        varname = str(series_with_duplicates.name)
        cdf_col = f"{varname}_emp_cdf"
        # With False, each row gets a distinct plotting position even for ties
        assert df[cdf_col].nunique() == len(df), (
            "With assign_dup_vals_max_return=False, all CDF values should be distinct"
        )
