"""GIS read and masking utilities for ss-fha.

All functions raise `ss_fha.exceptions.DataError` on failure.

Design notes
------------
- `read_shapefile` accepts `clip_to: gpd.GeoDataFrame | None`. Callers must
  pass this argument explicitly — `None` means "no clipping needed" (e.g.,
  when reading the watershed polygon itself). There is no silent default.
- `crs_epsg` in `create_mask_from_shapefile` and `rasterize_features` is a
  required argument. CRS reprojection happens inside these functions so callers
  do not need to manage CRS alignment manually.
- All spatial operations assume the reference dataset has `x` and `y`
  coordinates and a valid `rio` (rioxarray) accessor.
"""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import xarray as xr

from ss_fha.exceptions import DataError


def read_shapefile(
    path: Path,
    clip_to: gpd.GeoDataFrame | None,
) -> gpd.GeoDataFrame:
    """Read a shapefile (or any OGR-readable vector file) into a GeoDataFrame.

    Parameters
    ----------
    path:
        Path to the shapefile (or GeoPackage, GeoJSON, etc.).
    clip_to:
        If provided, clip the loaded GeoDataFrame to the bounding geometry of
        this GeoDataFrame before returning. The clip is performed in the CRS of
        ``clip_to``; the result is re-projected back to the original file CRS.
        Pass ``None`` when no clipping is needed (e.g., loading the watershed
        boundary polygon itself).

    Returns
    -------
    gpd.GeoDataFrame

    Raises
    ------
    DataError
        If the file does not exist, cannot be read, or clipping fails.
    """
    path = Path(path)

    if not path.exists():
        raise DataError(
            operation="read shapefile",
            filepath=path,
            reason="Path does not exist.",
        )

    try:
        gdf = gpd.read_file(path)
    except Exception as e:
        raise DataError(
            operation="read shapefile",
            filepath=path,
            reason=str(e),
        ) from e

    if clip_to is not None:
        try:
            original_crs = gdf.crs
            clip_crs = clip_to.crs
            gdf = gdf.to_crs(clip_crs)
            gdf = gpd.clip(gdf, clip_to)
            gdf = gdf.to_crs(original_crs)
        except Exception as e:
            raise DataError(
                operation="clip shapefile",
                filepath=path,
                reason=str(e),
            ) from e

    return gdf


def create_mask_from_shapefile(
    shapefile_path: Path,
    reference_ds: xr.Dataset,
    crs_epsg: int,
) -> xr.DataArray:
    """Create a boolean DataArray mask from a shapefile polygon.

    The shapefile is re-projected to ``crs_epsg`` before masking to ensure
    alignment with the reference dataset's spatial transform. Cells inside
    any polygon are ``True``; cells outside are ``False``.

    Parameters
    ----------
    shapefile_path:
        Path to the shapefile whose polygons define the mask.
    reference_ds:
        xarray Dataset with ``x`` and ``y`` coordinates and a valid
        ``rio`` accessor (requires rioxarray).
    crs_epsg:
        EPSG code of the CRS used by ``reference_ds``. The shapefile will
        be re-projected to this CRS before masking.

    Returns
    -------
    xr.DataArray
        Boolean DataArray with the same ``x``/``y`` coordinates as
        ``reference_ds``, with ``True`` inside the shapefile polygons.

    Raises
    ------
    DataError
        If the shapefile cannot be read, if ``reference_ds`` lacks the
        expected spatial coordinates/accessor, or if masking fails.
    """
    import rasterio.features
    from shapely.geometry import mapping

    shapefile_path = Path(shapefile_path)

    try:
        gdf = gpd.read_file(shapefile_path)
    except Exception as e:
        raise DataError(
            operation="read shapefile for masking",
            filepath=shapefile_path,
            reason=str(e),
        ) from e

    try:
        gdf = gdf.to_crs(epsg=crs_epsg)
    except Exception as e:
        raise DataError(
            operation="reproject shapefile to crs_epsg",
            filepath=shapefile_path,
            reason=str(e),
        ) from e

    # Validate spatial structure of reference dataset
    for coord in ("x", "y"):
        if coord not in reference_ds.coords:
            raise DataError(
                operation="create mask from shapefile",
                filepath=shapefile_path,
                reason=(
                    f"reference_ds is missing '{coord}' coordinate. "
                    "Dataset must have x and y spatial coordinates."
                ),
            )

    # Use the first data variable to get a representative DataArray
    first_var = next(iter(reference_ds.data_vars))
    da_ref = reference_ds[first_var]

    try:
        shapes = [mapping(geom) for geom in gdf.geometry]
        mask_array = rasterio.features.geometry_mask(
            shapes,
            transform=da_ref.rio.transform(),
            invert=True,
            out_shape=da_ref.shape[-2:],
        )
    except Exception as e:
        raise DataError(
            operation="rasterize shapefile geometry for mask",
            filepath=shapefile_path,
            reason=str(e),
        ) from e

    # Build a DataArray with the same x/y coordinates
    import numpy as np

    mask_da = xr.DataArray(
        mask_array,
        dims=["y", "x"],
        coords={"y": reference_ds.y, "x": reference_ds.x},
    )
    return mask_da


def rasterize_features(
    gdf: gpd.GeoDataFrame,
    reference_ds: xr.Dataset,
    field: str | None,
) -> xr.DataArray:
    """Rasterize GeoDataFrame features onto a reference grid.

    Each feature is burned as an integer ID. If ``field`` is provided,
    the values in that column are used as the burn value; otherwise,
    features are assigned sequential integer IDs (1-based). Background
    cells (not covered by any feature) are set to ``-9999``.

    Parameters
    ----------
    gdf:
        GeoDataFrame whose geometries will be rasterized. Must already be
        in the same CRS as ``reference_ds``.
    reference_ds:
        xarray Dataset with ``x`` and ``y`` coordinates and a valid
        ``rio`` accessor (requires rioxarray).
    field:
        Column in ``gdf`` to use as burn value. Pass ``None`` to use
        sequential 1-based integer IDs.

    Returns
    -------
    xr.DataArray
        Integer DataArray (dtype int32) with the same ``x``/``y``
        coordinates as ``reference_ds``. Background = ``-9999``.

    Raises
    ------
    DataError
        If ``field`` is not found in ``gdf``, if ``reference_ds`` lacks
        spatial coordinates, or if rasterization fails.
    """
    import numpy as np
    import rasterio.features
    from shapely.geometry import mapping

    if field is not None and field not in gdf.columns:
        raise DataError(
            operation="rasterize features",
            filepath=Path("<GeoDataFrame>"),
            reason=f"Field '{field}' not found in GeoDataFrame columns: {list(gdf.columns)}",
        )

    for coord in ("x", "y"):
        if coord not in reference_ds.coords:
            raise DataError(
                operation="rasterize features",
                filepath=Path("<GeoDataFrame>"),
                reason=(
                    f"reference_ds is missing '{coord}' coordinate. "
                    "Dataset must have x and y spatial coordinates."
                ),
            )

    first_var = next(iter(reference_ds.data_vars))
    da_ref = reference_ds[first_var]
    out_shape = da_ref.shape[-2:]

    try:
        if field is not None:
            shapes = [
                (mapping(row.geometry), int(row[field]))
                for _, row in gdf.iterrows()
            ]
        else:
            shapes = [
                (mapping(row.geometry), idx + 1)
                for idx, (_, row) in enumerate(gdf.iterrows())
            ]

        rasterized = rasterio.features.rasterize(
            shapes,
            out_shape=out_shape,
            transform=da_ref.rio.transform(),
            fill=-9999,
            dtype="int32",
        )
    except Exception as e:
        raise DataError(
            operation="rasterize features",
            filepath=Path("<GeoDataFrame>"),
            reason=str(e),
        ) from e

    return xr.DataArray(
        rasterized,
        dims=["y", "x"],
        coords={"y": reference_ds.y, "x": reference_ds.x},
    )
