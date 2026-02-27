"""Core geospatial computation functions for ss-fha.

All functions here are pure computation — no I/O, no file operations,
no side effects. They operate on already-loaded xarray and numpy objects.

I/O boundary
------------
This module sits strictly on the computation side of the I/O boundary:

- File loading (shapefiles, GeoJSON, GeoPackage) → ``ss_fha.io.gis_io``
- Masking from a file path or in-memory geometry → ``ss_fha.io.gis_io.create_mask_from_polygon``
- Rasterizing feature GeoDataFrames to a grid → ``ss_fha.io.gis_io.rasterize_features``
- Everything here → operates on the already-rasterized ``xr.DataArray`` results of the above

CRS policy
----------
No function in this module reads or writes files, so CRS reprojection is never
performed here. Callers are responsible for ensuring that any DataArrays passed
in share the same CRS. The ``crs_epsg`` argument present in ``gis_io`` functions
is intentionally absent here.

Grid geometry
-------------
``grid_cell_size_m`` returns the grid cell size in metres. It raises
``ComputationError`` if the grid is non-square (x and y cell sizes differ),
which would cause area computations to silently use the wrong value in the
old code. Fail-fast is the correct behaviour here.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import xarray as xr

from ss_fha.exceptions import ComputationError


# ---------------------------------------------------------------------------
# Grid utilities
# ---------------------------------------------------------------------------


def grid_cell_size_m(ds: xr.Dataset | xr.DataArray) -> float:
    """Return the grid cell size in metres from a spatially regular Dataset.

    Uses the mode of the first-difference of sorted x coordinates as the cell
    size, which is robust to floating-point noise on regular grids. Raises if
    the x and y cell sizes differ, since area computations require a square
    grid.

    Parameters
    ----------
    ds:
        xarray Dataset or DataArray with ``x`` and ``y`` coordinates on a
        regular spatial grid.

    Returns
    -------
    float
        Grid cell size in metres (same units as the x/y coordinates).

    Raises
    ------
    ComputationError
        If the grid is non-square (x cell size != y cell size).
    """
    x_size = float(
        ds.x.to_series().sort_values().diff().dropna().mode().iloc[0]
    )
    y_size = float(
        ds.y.to_series().sort_values().diff().dropna().abs().mode().iloc[0]
    )

    if not np.isclose(x_size, y_size):
        raise ComputationError(
            f"grid_cell_size_m: grid is not square — "
            f"x cell size = {x_size:.4f} m, y cell size = {y_size:.4f} m. "
            "Area computations require a square grid."
        )

    return x_size


# ---------------------------------------------------------------------------
# Feature impact identification
# ---------------------------------------------------------------------------


def _retrieve_unique_feature_indices(
    x: np.ndarray,
    sorted_unique_features_in_aoi: np.ndarray,
) -> np.ndarray:
    """Return a boolean mask indicating which AOI features appear in ``x``.

    This is the ufunc kernel called by ``return_impacted_features`` via
    ``xr.apply_ufunc``. It operates on a single (x, y) spatial slice for
    one event.

    Parameters
    ----------
    x:
        Flattened array of rasterized feature IDs for one event (output of
        ``gis_io.rasterize_features`` sliced to a single event).
    sorted_unique_features_in_aoi:
        Sorted 1-D array of the unique integer feature IDs present in the
        AOI. Used as the reference set for ``np.isin``.

    Returns
    -------
    np.ndarray
        Boolean array of length ``len(sorted_unique_features_in_aoi)``.
        Element ``i`` is ``True`` if feature ``sorted_unique_features_in_aoi[i]``
        appears anywhere in ``x``.
    """
    unique_impacted = np.unique(x)
    return np.isin(
        sorted_unique_features_in_aoi,
        unique_impacted,
        assume_unique=True,
    )


def return_impacted_features(
    da_features_rasterized: xr.DataArray,
    sorted_unique_features_in_aoi: np.ndarray,
    event_iloc_chunksize: int,
) -> xr.DataArray:
    """Identify which AOI features are impacted in each simulated event.

    For every event in ``da_features_rasterized``, determines which of the
    features in ``sorted_unique_features_in_aoi`` are present (i.e., have
    at least one rasterized grid cell with flood depth above the threshold
    already applied upstream by the caller).

    Parameters
    ----------
    da_features_rasterized:
        3-D DataArray with dimensions ``(event_iloc, y, x)``. Values are
        integer feature IDs (from ``gis_io.rasterize_features``) where the
        flood depth exceeds a threshold; background cells = ``-9999``.
        The DataArray's ``.name`` attribute is used as the feature type
        label (e.g., ``"roads"``, ``"buildings"``).
    sorted_unique_features_in_aoi:
        Sorted 1-D integer array of all feature IDs present in the AOI.
        Determines the output coordinate on the new feature dimension.
    event_iloc_chunksize:
        Dask chunk size along the ``event_iloc`` dimension. Controls
        parallelism for large ensembles.

    Returns
    -------
    xr.DataArray
        Boolean DataArray with dimensions ``(event_iloc, <feature_id_name>)``.
        ``True`` where the feature was impacted in that event.
        Named ``"<feature_id_name>_impacted"``.

    Raises
    ------
    ComputationError
        If ``da_features_rasterized`` has no ``.name`` set.
    """
    if not da_features_rasterized.name:
        raise ComputationError(
            "return_impacted_features: da_features_rasterized must have a "
            ".name attribute (e.g., 'roads', 'buildings') — it is used as "
            "the feature dimension name in the output."
        )

    feature_id_name = da_features_rasterized.name
    n_features_in_aoi = len(sorted_unique_features_in_aoi)

    da_chunked = da_features_rasterized.chunk(
        {"x": -1, "y": -1, "event_iloc": event_iloc_chunksize}
    )

    da_impacted = xr.apply_ufunc(
        _retrieve_unique_feature_indices,
        da_chunked,
        input_core_dims=[["x", "y"]],
        output_core_dims=[[feature_id_name]],
        vectorize=True,
        dask="parallelized",
        output_dtypes=[bool],
        keep_attrs=True,
        kwargs={"sorted_unique_features_in_aoi": sorted_unique_features_in_aoi},
        dask_gufunc_kwargs={"output_sizes": {feature_id_name: n_features_in_aoi}},
    )

    da_impacted[feature_id_name] = sorted_unique_features_in_aoi.astype(int)
    da_impacted.name = f"{feature_id_name}_impacted"
    return da_impacted


# ---------------------------------------------------------------------------
# Feature count helpers
# ---------------------------------------------------------------------------


def _count_impacted_features(x: np.ndarray) -> int:
    """Return the count of ``True`` values in a 1-D boolean array.

    Ufunc kernel for ``return_number_of_impacted_features``.

    Parameters
    ----------
    x:
        1-D boolean array — one element per feature in the AOI.

    Returns
    -------
    int
        Count of ``True`` values.
    """
    return int(x.sum())


def return_number_of_impacted_features(
    da_impacted: xr.DataArray,
    feature_type: str,
) -> xr.DataArray:
    """Count the number of impacted features per event.

    Parameters
    ----------
    da_impacted:
        Boolean DataArray from ``return_impacted_features`` with dimensions
        ``(event_iloc, <feature_id_name>)``.
    feature_type:
        Label for the feature type (e.g., ``"roads"``, ``"buildings"``).
        Used to name the output DataArray.

    Returns
    -------
    xr.DataArray
        Integer DataArray with dimension ``event_iloc`` only.
        Named ``"n_<feature_type>_impacted"``.
    """
    da_loaded = da_impacted.load()
    feature_dim = da_loaded.dims[1]

    da_count = xr.apply_ufunc(
        _count_impacted_features,
        da_loaded,
        input_core_dims=[[feature_dim]],
        output_core_dims=[[]],
        vectorize=True,
        dask="parallelized",
        output_dtypes=[int],
        keep_attrs=True,
    )
    da_count.name = f"n_{feature_type}_impacted"
    return da_count


# ---------------------------------------------------------------------------
# Per-feature minimum impact return period
# ---------------------------------------------------------------------------


def compute_min_return_period_of_feature_impact(
    s_feature_impacted: pd.Series,  # type: ignore[type-arg]
    n_years: int,
    alpha: float,
    beta: float,
) -> float:
    """Return the minimum return period at which a single feature is impacted.

    Computes empirical return periods for the boolean impact series (True =
    impacted in that event), then returns the return period associated with the
    True group minimum — i.e., how rarely the feature needs to be impacted
    before it would be expected to be impacted.

    Returns ``nan`` if the feature was never impacted.

    Parameters
    ----------
    s_feature_impacted:
        Boolean pandas Series indexed by ``event_iloc``, where ``True``
        means the feature was impacted in that event.
    n_years:
        Total number of synthesised years in the stochastic weather record.
    alpha:
        Plotting position parameter (Weibull: 0.0).
    beta:
        Plotting position parameter (Weibull: 0.0).

    Returns
    -------
    float
        Minimum return period of impact in years, or ``nan`` if the feature
        was never impacted.
    """
    from ss_fha.core.event_statistics import _compute_return_periods_for_series

    varname = "feature_impacted"
    s = s_feature_impacted.copy()
    s.name = varname

    if not s.any():
        return float("nan")

    df_rtrn_pds = _compute_return_periods_for_series(
        s,
        n_years=n_years,
        alpha=alpha,
        beta=beta,
        varname=varname,
    )

    rtrn_pd_of_impact = float(
        df_rtrn_pds.groupby(varname).min().loc[True, f"{varname}_return_pd_yrs"]  # type: ignore[index]
    )
    return rtrn_pd_of_impact
