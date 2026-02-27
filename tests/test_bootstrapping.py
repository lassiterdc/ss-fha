"""Unit tests for ss_fha.core.bootstrapping (Work Chunk 02B).

Validation strategy
-------------------
1. ``draw_bootstrap_years``: reproducibility (same seed → same result),
   independence (different seed → different result), year pool correctness
   (draws from [0, n_years_synthesized), not from dataset years).
2. ``assemble_bootstrap_sample``: event-free years skipped, event numbers
   reassigned sequentially, NaN raises SSFHAError, empty result handled.
3. ``compute_return_period_indexed_depths``: output dimension is return_pd_yrs
   (not event_iloc), depths are sorted ascending, return period values are
   positive and consistent with ``calculate_return_period``.
4. Integration: full pipeline (draw → assemble → compute) produces return-period-
   indexed output that is consistent with direct application of flood_probability
   functions.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
import xarray as xr

from ss_fha.core.bootstrapping import (
    assemble_bootstrap_sample,
    compute_return_period_indexed_depths,
    draw_bootstrap_years,
    sort_last_dim,
)
from ss_fha.core.empirical_frequency_analysis import calculate_positions, calculate_return_period
from ss_fha.exceptions import SSFHAError


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def synthetic_flood_probs() -> xr.DataArray:
    """Small synthetic flood probability DataArray (5x5 grid, 20 events)."""
    rng = np.random.default_rng(0)
    nx, ny, n_events = 5, 5, 20
    data = rng.exponential(scale=0.5, size=(nx, ny, n_events)).astype("float32")
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


@pytest.fixture
def event_mapping() -> pd.DataFrame:
    """Event iloc mapping: 20 events across years 0–9 (2 events per year)."""
    years = np.repeat(np.arange(10), 2)
    event_ilocs = np.arange(20)
    return pd.DataFrame({"year": years, "event_iloc": event_ilocs})


# ---------------------------------------------------------------------------
# draw_bootstrap_years
# ---------------------------------------------------------------------------

class TestDrawBootstrapYears:

    def test_output_length_equals_n_years_synthesized(self):
        result = draw_bootstrap_years(n_years_synthesized=1000, base_seed=0, sample_id=0)
        assert len(result) == 1000

    def test_output_values_in_valid_range(self):
        result = draw_bootstrap_years(n_years_synthesized=100, base_seed=0, sample_id=0)
        assert np.all(result >= 0) and np.all(result < 100)

    def test_reproducibility(self):
        """Same base_seed + sample_id must produce identical results."""
        a = draw_bootstrap_years(n_years_synthesized=500, base_seed=42, sample_id=7)
        b = draw_bootstrap_years(n_years_synthesized=500, base_seed=42, sample_id=7)
        np.testing.assert_array_equal(a, b)

    def test_different_sample_ids_differ(self):
        """Different sample_ids must produce different year arrays."""
        a = draw_bootstrap_years(n_years_synthesized=500, base_seed=42, sample_id=0)
        b = draw_bootstrap_years(n_years_synthesized=500, base_seed=42, sample_id=1)
        assert not np.array_equal(a, b)

    def test_different_base_seeds_differ(self):
        """Different base_seeds must produce different year arrays."""
        a = draw_bootstrap_years(n_years_synthesized=500, base_seed=0, sample_id=0)
        b = draw_bootstrap_years(n_years_synthesized=500, base_seed=1, sample_id=0)
        assert not np.array_equal(a, b)

    def test_year_pool_is_full_range(self):
        """Years must be drawn from np.arange(n_years_synthesized), not a subset.

        This is the correctness-critical year-pool test: if years are drawn
        only from years-with-events (e.g. 954 of 1000), the effective
        denominator shrinks and return periods are overstated.
        """
        # With 1000 draws from [0, 1000) we expect all values to appear
        # (probability of missing any value ≈ e^{-1} ≈ 37% per value, but
        # for 1000 values over 5000 draws the chance of missing the endpoints
        # is negligible). Instead, just verify the max can reach n-1.
        result = draw_bootstrap_years(n_years_synthesized=50, base_seed=0, sample_id=0)
        # With 50 draws from [0,50), virtually certain to see values near both ends
        # Use a large draw to reliably hit both 0 and 49
        result_large = draw_bootstrap_years(n_years_synthesized=50, base_seed=0, sample_id=999)
        # Collect across many seeds
        all_values = set()
        for sid in range(100):
            all_values.update(
                draw_bootstrap_years(n_years_synthesized=50, base_seed=0, sample_id=sid).tolist()
            )
        assert 0 in all_values, "Year 0 should appear in pool"
        assert 49 in all_values, "Year 49 (n-1) should appear in pool"


# ---------------------------------------------------------------------------
# assemble_bootstrap_sample
# ---------------------------------------------------------------------------

class TestAssembleBootstrapSample:

    def test_output_has_event_iloc_dim(self, synthetic_flood_probs, event_mapping):
        resampled = np.array([0, 1, 2, 3, 4])  # 5 years, 2 events each = 10 events
        years_with_events = np.arange(10)
        result = assemble_bootstrap_sample(
            resampled, years_with_events, event_mapping, synthetic_flood_probs
        )
        assert "event_iloc" in result.dims

    def test_event_ilocs_are_sequential_from_zero(self, synthetic_flood_probs, event_mapping):
        resampled = np.array([0, 1, 2])  # 6 events
        years_with_events = np.arange(10)
        result = assemble_bootstrap_sample(
            resampled, years_with_events, event_mapping, synthetic_flood_probs
        )
        expected_ilocs = np.arange(len(result.event_iloc))
        np.testing.assert_array_equal(result.event_iloc.values, expected_ilocs)

    def test_event_free_years_are_skipped(self, synthetic_flood_probs, event_mapping):
        """Only years 0-9 have events. Resampling years 10-99 produces zero events."""
        resampled = np.array([50, 60, 70, 80])  # all event-free
        years_with_events = np.arange(10)
        result = assemble_bootstrap_sample(
            resampled, years_with_events, event_mapping, synthetic_flood_probs
        )
        assert result.sizes["event_iloc"] == 0

    def test_duplicate_years_include_events_twice(self, synthetic_flood_probs, event_mapping):
        """Year 0 has 2 events. Drawing it twice produces 4 events."""
        resampled = np.array([0, 0])
        years_with_events = np.arange(10)
        result = assemble_bootstrap_sample(
            resampled, years_with_events, event_mapping, synthetic_flood_probs
        )
        assert result.sizes["event_iloc"] == 4

    def test_nan_in_input_raises(self, event_mapping):
        """NaN in flood depth DataArray must raise SSFHAError with diagnostic message."""
        rng = np.random.default_rng(1)
        data = rng.exponential(scale=0.5, size=(3, 3, 10)).astype("float32")
        data[0, 0, 0] = np.nan  # inject NaN
        da = xr.DataArray(
            data,
            dims=["x", "y", "event_iloc"],
            coords={"x": np.arange(3, dtype=float),
                    "y": np.arange(3, dtype=float),
                    "event_iloc": np.arange(10)},
            name="flood_depth",
        )
        mapping = pd.DataFrame({
            "year": np.repeat(np.arange(5), 2),
            "event_iloc": np.arange(10),
        })
        resampled = np.array([0, 1])
        with pytest.raises(SSFHAError, match="NaN values found"):
            assemble_bootstrap_sample(
                resampled, np.arange(5), mapping, da
            )

    def test_nan_error_message_is_diagnostic(self, event_mapping):
        """Error message must prompt investigation, not just report NaN count."""
        rng = np.random.default_rng(2)
        data = rng.exponential(scale=0.5, size=(2, 2, 4)).astype("float32")
        data[0, 0, 0] = np.nan
        da = xr.DataArray(
            data,
            dims=["x", "y", "event_iloc"],
            coords={"x": np.arange(2, dtype=float),
                    "y": np.arange(2, dtype=float),
                    "event_iloc": np.arange(4)},
            name="flood_depth",
        )
        mapping = pd.DataFrame({
            "year": np.repeat(np.arange(2), 2),
            "event_iloc": np.arange(4),
        })
        with pytest.raises(SSFHAError) as exc_info:
            assemble_bootstrap_sample(
                np.array([0, 1]), np.arange(2), mapping, da
            )
        msg = str(exc_info.value)
        assert "investigate" in msg.lower() or "corrupted" in msg.lower() or "0.0" in msg

    def test_spatial_dims_preserved(self, synthetic_flood_probs, event_mapping):
        resampled = np.array([0, 1])
        years_with_events = np.arange(10)
        result = assemble_bootstrap_sample(
            resampled, years_with_events, event_mapping, synthetic_flood_probs
        )
        assert result.sizes["x"] == synthetic_flood_probs.sizes["x"]
        assert result.sizes["y"] == synthetic_flood_probs.sizes["y"]


# ---------------------------------------------------------------------------
# sort_last_dim
# ---------------------------------------------------------------------------

class TestSortLastDim:

    def test_sorts_ascending(self):
        arr = np.array([3.0, 1.0, 4.0, 1.0, 5.0])
        result = sort_last_dim(arr)
        np.testing.assert_array_equal(result, np.sort(arr))

    def test_2d_sorts_along_last_axis(self):
        arr = np.array([[3.0, 1.0, 2.0], [9.0, 5.0, 7.0]])
        result = sort_last_dim(arr)
        for row_idx in range(arr.shape[0]):
            np.testing.assert_array_equal(result[row_idx], np.sort(arr[row_idx]))

    def test_shape_preserved(self):
        arr = np.random.default_rng(0).random((4, 5, 6))
        assert sort_last_dim(arr).shape == arr.shape


# ---------------------------------------------------------------------------
# compute_return_period_indexed_depths
# ---------------------------------------------------------------------------

class TestComputeReturnPeriodIndexedDepths:

    @pytest.fixture
    def small_stacked(self) -> xr.DataArray:
        """3x3 grid, 15 events, no NaNs."""
        rng = np.random.default_rng(10)
        data = rng.exponential(scale=1.0, size=(3, 3, 15)).astype("float32")
        return xr.DataArray(
            data,
            dims=["x", "y", "event_iloc"],
            coords={"x": np.arange(3, dtype=float),
                    "y": np.arange(3, dtype=float),
                    "event_iloc": np.arange(15)},
            name="flood_depth",
        )

    def test_output_dim_is_return_pd_yrs(self, small_stacked):
        result = compute_return_period_indexed_depths(
            small_stacked, alpha=0.0, beta=0.0, n_years=1000
        )
        assert "return_pd_yrs" in result.dims
        assert "event_iloc" not in result.dims

    def test_return_pd_yrs_coordinate_is_positive(self, small_stacked):
        result = compute_return_period_indexed_depths(
            small_stacked, alpha=0.0, beta=0.0, n_years=1000
        )
        assert np.all(result.return_pd_yrs.values > 0)

    def test_return_pd_yrs_coordinate_is_sorted_ascending(self, small_stacked):
        result = compute_return_period_indexed_depths(
            small_stacked, alpha=0.0, beta=0.0, n_years=1000
        )
        rp = result.return_pd_yrs.values
        np.testing.assert_array_equal(rp, np.sort(rp))

    def test_depths_sorted_ascending_at_each_gridcell(self, small_stacked):
        result = compute_return_period_indexed_depths(
            small_stacked, alpha=0.0, beta=0.0, n_years=1000
        )
        for xi in range(result.sizes["x"]):
            for yi in range(result.sizes["y"]):
                depths = result.isel(x=xi, y=yi).values
                np.testing.assert_array_equal(depths, np.sort(depths))

    def test_output_shape_matches_input_spatial_dims(self, small_stacked):
        result = compute_return_period_indexed_depths(
            small_stacked, alpha=0.0, beta=0.0, n_years=1000
        )
        assert result.sizes["x"] == small_stacked.sizes["x"]
        assert result.sizes["y"] == small_stacked.sizes["y"]
        assert result.sizes["return_pd_yrs"] == small_stacked.sizes["event_iloc"]

    def test_return_periods_consistent_with_flood_probability_functions(self, small_stacked):
        """Return period coordinate must match direct calculate_positions + calculate_return_period."""
        alpha, beta, n_years = 0.0, 0.0, 1000
        n_events = small_stacked.sizes["event_iloc"]

        result = compute_return_period_indexed_depths(
            small_stacked, alpha=alpha, beta=beta, n_years=n_years
        )

        # Compute expected return periods from representative series
        representative = small_stacked.max(["x", "y"]).values
        positions = np.sort(
            calculate_positions(representative, alpha=alpha, beta=beta, fillna_val=0.0)
        )
        expected_rp = calculate_return_period(positions, n_years=n_years, n_events=n_events)

        np.testing.assert_allclose(result.return_pd_yrs.values, expected_rp, rtol=1e-5)

    def test_empty_stacked_raises(self):
        """Zero-event DataArray must raise SSFHAError."""
        da = xr.DataArray(
            np.empty((3, 3, 0), dtype="float32"),
            dims=["x", "y", "event_iloc"],
            coords={"x": np.arange(3, dtype=float),
                    "y": np.arange(3, dtype=float),
                    "event_iloc": np.array([], dtype=int)},
            name="flood_depth",
        )
        with pytest.raises(SSFHAError, match="zero events"):
            compute_return_period_indexed_depths(da, alpha=0.0, beta=0.0, n_years=1000)

    def test_n_years_affects_return_periods(self, small_stacked):
        """Doubling n_years must double the return period coordinate values."""
        rp_1000 = compute_return_period_indexed_depths(
            small_stacked, alpha=0.0, beta=0.0, n_years=1000
        ).return_pd_yrs.values
        rp_2000 = compute_return_period_indexed_depths(
            small_stacked, alpha=0.0, beta=0.0, n_years=2000
        ).return_pd_yrs.values
        np.testing.assert_allclose(rp_2000, rp_1000 * 2, rtol=1e-5)


# ---------------------------------------------------------------------------
# Integration: draw → assemble → compute
# ---------------------------------------------------------------------------

class TestBootstrapIntegration:

    def test_full_pipeline_produces_valid_output(self, synthetic_flood_probs, event_mapping):
        """End-to-end: draw years → assemble sample → compute return period depths."""
        years_with_events = np.arange(10)
        n_years_synthesized = 100

        resampled = draw_bootstrap_years(
            n_years_synthesized=n_years_synthesized, base_seed=0, sample_id=0
        )
        stacked = assemble_bootstrap_sample(
            resampled, years_with_events, event_mapping, synthetic_flood_probs
        )

        if stacked.sizes["event_iloc"] == 0:
            pytest.skip("All resampled years were event-free — edge case, not an error")

        result = compute_return_period_indexed_depths(
            stacked, alpha=0.0, beta=0.0, n_years=n_years_synthesized
        )

        assert "return_pd_yrs" in result.dims
        assert np.all(result.return_pd_yrs.values > 0)
        assert not np.isnan(result.values).any()

    def test_two_samples_with_same_seed_are_identical(
        self, synthetic_flood_probs, event_mapping
    ):
        """Same base_seed + sample_id must produce identical final outputs."""
        years_with_events = np.arange(10)
        n_years_synthesized = 100

        def run(sample_id):
            resampled = draw_bootstrap_years(100, base_seed=7, sample_id=sample_id)
            stacked = assemble_bootstrap_sample(
                resampled, years_with_events, event_mapping, synthetic_flood_probs
            )
            if stacked.sizes["event_iloc"] == 0:
                return None
            return compute_return_period_indexed_depths(
                stacked, alpha=0.0, beta=0.0, n_years=n_years_synthesized
            )

        result_a = run(sample_id=3)
        result_b = run(sample_id=3)

        if result_a is None or result_b is None:
            pytest.skip("Edge case: all-event-free sample")

        np.testing.assert_array_equal(result_a.values, result_b.values)
        np.testing.assert_array_equal(
            result_a.return_pd_yrs.values, result_b.return_pd_yrs.values
        )
