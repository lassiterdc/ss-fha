"""GIS file loading and spatial masking utilities for ss-fha.

All functions raise `ss_fha.exceptions.DataError` on failure.

Design notes
------------
- ``load_geospatial_data_from_file`` is the canonical loader for any OGR-readable
  vector format. It validates the file extension and is the only place in the
  codebase that calls ``gpd.read_file`` directly. Supported extensions:
  ``.shp``, ``.geojson``, ``.json``, ``.gpkg``.
- Function names never include filetype strings (``shapefile``, ``geojson``,
  etc.) unless the function is exclusively a file-reading or file-writing
  operation. ``load_geospatial_data_from_file`` is the sole exception.
- ``create_mask_from_polygon`` accepts a file path, a GeoDataFrame, a
  GeoSeries, or a Shapely geometry — callers do not need to pre-load data.
- ``crs_epsg`` in ``create_mask_from_polygon`` and ``rasterize_features`` is a
  required argument. CRS reprojection happens inside these functions so callers
  do not need to manage CRS alignment manually.
- All spatial operations assume the reference dataset has ``x`` and ``y``
  coordinates and a valid ``rio`` (rioxarray) accessor.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Union

import geopandas as gpd
import xarray as xr

from ss_fha.exceptions import DataError

if TYPE_CHECKING:
    from shapely.geometry.base import BaseGeometry

# Supported geospatial file extensions for load_geospatial_data_from_file.
# Update this set when adding support for new formats.
_SUPPORTED_GEO_EXTENSIONS = {".shp", ".geojson", ".json", ".gpkg"}

# Type alias for the range of geometry inputs accepted by create_mask_from_polygon
GeometryInput = Union[
    Path,
    str,
    gpd.GeoDataFrame,
    gpd.GeoSeries,
    "BaseGeometry",
]


def load_geospatial_data_from_file(
    path: Path | str,
    clip_to: gpd.GeoDataFrame | None,
) -> gpd.GeoDataFrame:
    """Load a vector geospatial file into a GeoDataFrame.

    This is the canonical loader for all geospatial file input in ss-fha.
    Supported formats: ``.shp``, ``.geojson``, ``.json``, ``.gpkg``.

    Parameters
    ----------
    path:
        Path to the geospatial file.
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
        If the extension is not supported, the file does not exist, cannot be
        read, or clipping fails.
    """
    path = Path(path)

    if path.suffix.lower() not in _SUPPORTED_GEO_EXTENSIONS:
        raise DataError(
            operation="load geospatial data from file",
            filepath=path,
            reason=(
                f"Unsupported file extension '{path.suffix}'. Supported extensions: {sorted(_SUPPORTED_GEO_EXTENSIONS)}"
            ),
        )

    if not path.exists():
        raise DataError(
            operation="load geospatial data from file",
            filepath=path,
            reason="Path does not exist.",
        )

    try:
        gdf = gpd.read_file(path)
    except Exception as e:
        raise DataError(
            operation="load geospatial data from file",
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
                operation="clip geospatial data",
                filepath=path,
                reason=str(e),
            ) from e

    return gdf


def create_mask_from_polygon(
    polygon: GeometryInput,
    reference_ds: xr.Dataset,
    crs_epsg: int,
) -> xr.DataArray:
    """Create a boolean DataArray mask from a polygon geometry.

    Cells inside any polygon are ``True``; cells outside are ``False``.
    The input geometry is re-projected to ``crs_epsg`` before masking to
    ensure alignment with the reference dataset's spatial transform.

    Parameters
    ----------
    polygon:
        The polygon(s) defining the mask. Accepts any of:

        - A ``Path`` or ``str`` file path to a supported geospatial file
          (``.shp``, ``.geojson``, ``.json``, ``.gpkg``). The file is loaded
          via ``load_geospatial_data_from_file`` (no clipping).
        - A ``gpd.GeoDataFrame`` — all features are used.
        - A ``gpd.GeoSeries`` — all geometries are used.
        - A Shapely ``Polygon`` or ``MultiPolygon`` geometry.

    reference_ds:
        xarray Dataset with ``x`` and ``y`` coordinates and a valid
        ``rio`` accessor (requires rioxarray).
    crs_epsg:
        EPSG code of the CRS used by ``reference_ds``. The input geometry
        will be re-projected to this CRS before masking.

    Returns
    -------
    xr.DataArray
        Boolean DataArray with the same ``x``/``y`` coordinates as
        ``reference_ds``, with ``True`` inside the polygon(s).

    Raises
    ------
    DataError
        If the input type is unsupported, the file cannot be read, if
        ``reference_ds`` lacks the expected spatial coordinates/accessor,
        or if masking fails.
    """
    import rasterio.features
    from shapely.geometry import mapping
    from shapely.geometry.base import BaseGeometry

    # Resolve input to a list of Shapely geometries in some CRS, then reproject.
    # For file path and GeoDataFrame inputs we can reproject via geopandas.
    # For bare Shapely geometries we assume the caller has already matched CRS
    # (no CRS metadata is available on a bare geometry).
    source_label = "<geometry>"

    if isinstance(polygon, (str, Path)):
        source_label = str(polygon)
        gdf = load_geospatial_data_from_file(Path(polygon), clip_to=None)
        try:
            gdf = gdf.to_crs(epsg=crs_epsg)
        except Exception as e:
            raise DataError(
                operation="reproject polygon to crs_epsg",
                filepath=Path(polygon),
                reason=str(e),
            ) from e
        geometries = list(gdf.geometry)

    elif isinstance(polygon, gpd.GeoDataFrame):
        try:
            gdf = polygon.to_crs(epsg=crs_epsg)
        except Exception as e:
            raise DataError(
                operation="reproject GeoDataFrame to crs_epsg",
                filepath=Path(source_label),
                reason=str(e),
            ) from e
        geometries = list(gdf.geometry)

    elif isinstance(polygon, gpd.GeoSeries):
        try:
            gs = polygon.to_crs(epsg=crs_epsg)
        except Exception as e:
            raise DataError(
                operation="reproject GeoSeries to crs_epsg",
                filepath=Path(source_label),
                reason=str(e),
            ) from e
        geometries = list(gs)

    elif isinstance(polygon, BaseGeometry):
        # Bare Shapely geometry — no CRS metadata available; caller is
        # responsible for providing a geometry already in crs_epsg.
        geometries = [polygon]

    else:
        raise DataError(
            operation="create mask from polygon",
            filepath=Path(source_label),
            reason=(
                f"Unsupported polygon input type: {type(polygon).__name__}. "
                "Expected a file path, GeoDataFrame, GeoSeries, or Shapely geometry."
            ),
        )

    # Validate spatial structure of reference dataset
    for coord in ("x", "y"):
        if coord not in reference_ds.coords:
            raise DataError(
                operation="create mask from polygon",
                filepath=Path(source_label),
                reason=(
                    f"reference_ds is missing '{coord}' coordinate. Dataset must have x and y spatial coordinates."
                ),
            )

    first_var = next(iter(reference_ds.data_vars))
    da_ref = reference_ds[first_var]

    try:
        shapes = [mapping(geom) for geom in geometries]
        mask_array = rasterio.features.geometry_mask(
            shapes,
            transform=da_ref.rio.transform(),
            invert=True,
            out_shape=(da_ref.sizes["y"], da_ref.sizes["x"]),
        )
    except Exception as e:
        raise DataError(
            operation="rasterize polygon geometry for mask",
            filepath=Path(source_label),
            reason=str(e),
        ) from e

    return xr.DataArray(
        mask_array,
        dims=["y", "x"],
        coords={"y": reference_ds.y, "x": reference_ds.x},
    )


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
                    f"reference_ds is missing '{coord}' coordinate. Dataset must have x and y spatial coordinates."
                ),
            )

    first_var = next(iter(reference_ds.data_vars))
    da_ref = reference_ds[first_var]
    out_shape = (da_ref.sizes["y"], da_ref.sizes["x"])

    try:
        if field is not None:
            shapes = [(mapping(row.geometry), int(row[field])) for _, row in gdf.iterrows()]
        else:
            shapes = [(mapping(row.geometry), idx + 1) for idx, (_, row) in enumerate(gdf.iterrows())]

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
