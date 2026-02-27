"""Tests for ss_fha.core.geospatial (Work Chunk 02D, Part B).

All tests use synthetic in-memory data — no real case study files required.
Geometries and grids are constructed with known properties so that correct
outputs can be verified analytically.
"""

from __future__ import annotations

import numpy as np
import pytest
import xarray as xr


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def square_grid_ds():
    """Small synthetic Dataset on a 50 m square grid (5x5, EPSG:32147-like)."""
    x = np.array([364000.0, 364050.0, 364100.0, 364150.0, 364200.0])
    y = np.array([4091200.0, 4091150.0, 4091100.0, 4091050.0, 4091000.0])
    data = np.zeros((5, 5), dtype="float32")
    return xr.Dataset(
        {"wlevel": xr.DataArray(data, dims=["y", "x"])},
        coords={"x": x, "y": y},
    )


@pytest.fixture
def nonsquare_grid_ds():
    """Dataset where x and y cell sizes differ."""
    x = np.array([0.0, 50.0, 100.0])
    y = np.array([0.0, 100.0, 200.0])  # 100 m steps vs 50 m x steps
    data = np.zeros((3, 3), dtype="float32")
    return xr.Dataset(
        {"wlevel": xr.DataArray(data, dims=["y", "x"])},
        coords={"x": x, "y": y},
    )


@pytest.fixture
def feature_da_3events():
    """
    Rasterized feature DataArray: 3 events × 3 y × 3 x.

    Feature IDs:
      - Feature 1 occupies cells (0,0), (0,1) in x/y
      - Feature 2 occupies cells (1,1), (1,2) in x/y
      - Background = -9999

    Event 0: only feature 1 cells have depths above threshold → features_da = 1s where feature 1
    Event 1: only feature 2 cells have depths above threshold → features_da = 2s where feature 2
    Event 2: both features impacted
    """
    # Shape: (event_iloc=3, y=3, x=3)
    data = np.full((3, 3, 3), -9999, dtype="int32")

    # Event 0: feature 1 impacted
    data[0, 0, 0] = 1
    data[0, 0, 1] = 1

    # Event 1: feature 2 impacted
    data[1, 1, 1] = 2
    data[1, 1, 2] = 2

    # Event 2: both impacted
    data[2, 0, 0] = 1
    data[2, 1, 1] = 2

    da = xr.DataArray(
        data,
        dims=["event_iloc", "y", "x"],
        coords={
            "event_iloc": [0, 1, 2],
            "y": [0.0, 1.0, 2.0],
            "x": [0.0, 1.0, 2.0],
        },
        name="roads",
    )
    return da


# ---------------------------------------------------------------------------
# grid_cell_size_m
# ---------------------------------------------------------------------------

class TestGridCellSizeM:
    def test_returns_correct_size(self, square_grid_ds):
        from ss_fha.core.geospatial import grid_cell_size_m

        size = grid_cell_size_m(square_grid_ds)
        assert size == pytest.approx(50.0)

    def test_accepts_dataarray(self, square_grid_ds):
        from ss_fha.core.geospatial import grid_cell_size_m

        size = grid_cell_size_m(square_grid_ds["wlevel"])
        assert size == pytest.approx(50.0)

    def test_nonsquare_grid_raises(self, nonsquare_grid_ds):
        from ss_fha.exceptions import ComputationError
        from ss_fha.core.geospatial import grid_cell_size_m

        with pytest.raises(ComputationError, match="not square"):
            grid_cell_size_m(nonsquare_grid_ds)


# ---------------------------------------------------------------------------
# return_impacted_features
# ---------------------------------------------------------------------------

class TestReturnImpactedFeatures:
    def test_output_shape(self, feature_da_3events):
        from ss_fha.core.geospatial import return_impacted_features

        sorted_features = np.array([1, 2])
        result = return_impacted_features(
            feature_da_3events,
            sorted_unique_features_in_aoi=sorted_features,
            event_iloc_chunksize=10,
        )

        # Expect (event_iloc=3, roads=2)
        assert result.dims == ("event_iloc", "roads")
        assert result.shape == (3, 2)

    def test_correct_impact_event0(self, feature_da_3events):
        """Event 0: only feature 1 impacted."""
        from ss_fha.core.geospatial import return_impacted_features

        sorted_features = np.array([1, 2])
        result = return_impacted_features(
            feature_da_3events,
            sorted_unique_features_in_aoi=sorted_features,
            event_iloc_chunksize=10,
        ).load()

        assert bool(result.sel(event_iloc=0, roads=1).values)
        assert not bool(result.sel(event_iloc=0, roads=2).values)

    def test_correct_impact_event1(self, feature_da_3events):
        """Event 1: only feature 2 impacted."""
        from ss_fha.core.geospatial import return_impacted_features

        sorted_features = np.array([1, 2])
        result = return_impacted_features(
            feature_da_3events,
            sorted_unique_features_in_aoi=sorted_features,
            event_iloc_chunksize=10,
        ).load()

        assert not bool(result.sel(event_iloc=1, roads=1).values)
        assert bool(result.sel(event_iloc=1, roads=2).values)

    def test_correct_impact_event2(self, feature_da_3events):
        """Event 2: both features impacted."""
        from ss_fha.core.geospatial import return_impacted_features

        sorted_features = np.array([1, 2])
        result = return_impacted_features(
            feature_da_3events,
            sorted_unique_features_in_aoi=sorted_features,
            event_iloc_chunksize=10,
        ).load()

        assert bool(result.sel(event_iloc=2, roads=1).values)
        assert bool(result.sel(event_iloc=2, roads=2).values)

    def test_output_dtype_is_bool(self, feature_da_3events):
        from ss_fha.core.geospatial import return_impacted_features

        sorted_features = np.array([1, 2])
        result = return_impacted_features(
            feature_da_3events,
            sorted_unique_features_in_aoi=sorted_features,
            event_iloc_chunksize=10,
        ).load()

        assert result.dtype == bool

    def test_output_name(self, feature_da_3events):
        from ss_fha.core.geospatial import return_impacted_features

        sorted_features = np.array([1, 2])
        result = return_impacted_features(
            feature_da_3events,
            sorted_unique_features_in_aoi=sorted_features,
            event_iloc_chunksize=10,
        )
        assert result.name == "roads_impacted"

    def test_unnamed_da_raises(self, feature_da_3events):
        from ss_fha.exceptions import ComputationError
        from ss_fha.core.geospatial import return_impacted_features

        da_unnamed = feature_da_3events.rename(None)
        with pytest.raises(ComputationError):
            return_impacted_features(
                da_unnamed,
                sorted_unique_features_in_aoi=np.array([1, 2]),
                event_iloc_chunksize=10,
            )


# ---------------------------------------------------------------------------
# return_number_of_impacted_features
# ---------------------------------------------------------------------------

class TestReturnNumberOfImpactedFeatures:
    def test_correct_counts(self, feature_da_3events):
        """Event 0 → 1 feature, Event 1 → 1 feature, Event 2 → 2 features."""
        from ss_fha.core.geospatial import (
            return_impacted_features,
            return_number_of_impacted_features,
        )

        sorted_features = np.array([1, 2])
        da_impacted = return_impacted_features(
            feature_da_3events,
            sorted_unique_features_in_aoi=sorted_features,
            event_iloc_chunksize=10,
        )
        result = return_number_of_impacted_features(da_impacted, "roads").load()

        assert int(result.sel(event_iloc=0).values) == 1
        assert int(result.sel(event_iloc=1).values) == 1
        assert int(result.sel(event_iloc=2).values) == 2

    def test_output_name(self, feature_da_3events):
        from ss_fha.core.geospatial import (
            return_impacted_features,
            return_number_of_impacted_features,
        )

        sorted_features = np.array([1, 2])
        da_impacted = return_impacted_features(
            feature_da_3events,
            sorted_unique_features_in_aoi=sorted_features,
            event_iloc_chunksize=10,
        )
        result = return_number_of_impacted_features(da_impacted, "roads")
        assert result.name == "n_roads_impacted"

    def test_output_has_only_event_iloc_dim(self, feature_da_3events):
        from ss_fha.core.geospatial import (
            return_impacted_features,
            return_number_of_impacted_features,
        )

        sorted_features = np.array([1, 2])
        da_impacted = return_impacted_features(
            feature_da_3events,
            sorted_unique_features_in_aoi=sorted_features,
            event_iloc_chunksize=10,
        )
        result = return_number_of_impacted_features(da_impacted, "roads")
        assert result.dims == ("event_iloc",)


# ---------------------------------------------------------------------------
# compute_min_return_period_of_feature_impact
# ---------------------------------------------------------------------------

class TestComputeMinReturnPeriodOfFeatureImpact:
    def test_never_impacted_returns_nan(self):
        """A feature that is never impacted returns nan."""
        import pandas as pd
        from ss_fha.core.geospatial import compute_min_return_period_of_feature_impact

        s = pd.Series([False, False, False], name="feature_impacted")
        result = compute_min_return_period_of_feature_impact(
            s, n_years=100, alpha=0.0, beta=0.0
        )
        assert np.isnan(result)

    def test_always_impacted_gives_short_return_period(self):
        """A feature impacted in every event has a short return period."""
        import pandas as pd
        from ss_fha.core.geospatial import compute_min_return_period_of_feature_impact

        n = 100
        s = pd.Series([True] * n, name="feature_impacted")
        result = compute_min_return_period_of_feature_impact(
            s, n_years=n, alpha=0.0, beta=0.0
        )
        # Weibull plotting position for the most common event ≈ 1/n * n_years ≈ 1 yr
        assert result == pytest.approx(1.0, rel=0.1)

    def test_return_period_positive_when_impacted(self):
        """Any impacted feature returns a positive return period."""
        import pandas as pd
        from ss_fha.core.geospatial import compute_min_return_period_of_feature_impact

        s = pd.Series(
            [True, False, True, False, False], name="feature_impacted"
        )
        result = compute_min_return_period_of_feature_impact(
            s, n_years=50, alpha=0.0, beta=0.0
        )
        assert result > 0
        assert not np.isnan(result)
