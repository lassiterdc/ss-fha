"""Tests for ss_fha.io (Work Chunk 01D).

All tests use synthetic in-memory data — no real case study files required.
GIS tests write temporary shapefiles to pytest's tmp_path.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
import xarray as xr


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def simple_dataset():
    """A small synthetic xarray Dataset with float and int variables."""
    x = np.array([0.0, 1.0, 2.0, 3.0])
    y = np.array([10.0, 11.0, 12.0])
    data_float = np.random.default_rng(42).random((3, 4)).astype("float32")
    data_int = np.arange(12, dtype="int32").reshape((3, 4))

    return xr.Dataset(
        {
            "flood_depth": xr.DataArray(data_float, dims=["y", "x"]),
            "event_id": xr.DataArray(data_int, dims=["y", "x"]),
        },
        coords={"x": x, "y": y},
    )


@pytest.fixture
def reference_ds_with_crs():
    """Synthetic spatial Dataset with rioxarray CRS attached (EPSG:32147)."""
    pytest.importorskip("rioxarray")
    import rioxarray  # noqa: F401

    x = np.linspace(364000.0, 364300.0, 4)
    y = np.linspace(4091300.0, 4091000.0, 3)
    data = np.zeros((3, 4), dtype="float32")

    ds = xr.Dataset(
        {"wlevel": xr.DataArray(data, dims=["y", "x"])},
        coords={"x": x, "y": y},
    )
    ds = ds.rio.write_crs("EPSG:32147")
    return ds


@pytest.fixture
def watershed_shapefile(tmp_path, reference_ds_with_crs):
    """Write a synthetic polygon that covers the entire reference_ds grid."""
    pytest.importorskip("geopandas")
    pytest.importorskip("shapely")
    import geopandas as gpd
    from shapely.geometry import box

    ds = reference_ds_with_crs
    xmin, xmax = float(ds.x.min()), float(ds.x.max())
    ymin, ymax = float(ds.y.min()), float(ds.y.max())

    # Expand slightly so all grid cells are inside
    poly = box(xmin - 50, ymin - 50, xmax + 50, ymax + 50)
    gdf = gpd.GeoDataFrame({"geometry": [poly]}, crs="EPSG:32147")

    shp_path = tmp_path / "watershed.shp"
    gdf.to_file(shp_path)
    return shp_path, gdf


# ---------------------------------------------------------------------------
# Import checks
# ---------------------------------------------------------------------------

def test_io_package_importable():
    """ss_fha.io package and all public names are importable."""
    from ss_fha.io import (  # noqa: F401
        create_mask_from_polygon,
        default_zarr_encoding,
        delete_zarr,
        load_geospatial_data_from_file,
        rasterize_features,
        read_netcdf,
        read_zarr,
        write_compressed_netcdf,
        write_zarr,
    )


# ---------------------------------------------------------------------------
# Zarr: encoding
# ---------------------------------------------------------------------------

def test_zarr_encoding_defaults(simple_dataset):
    """default_zarr_encoding returns a dict with entries for numeric vars."""
    from ss_fha.io.zarr_io import default_zarr_encoding

    encoding = default_zarr_encoding(simple_dataset, compression_level=5)

    assert isinstance(encoding, dict)
    assert "flood_depth" in encoding
    assert "event_id" in encoding


def test_zarr_encoding_has_compressor(simple_dataset):
    """Encoding entries for numeric vars include a 'compressors' key."""
    from ss_fha.io.zarr_io import default_zarr_encoding

    encoding = default_zarr_encoding(simple_dataset, compression_level=3)
    assert "compressors" in encoding["flood_depth"]
    assert "compressors" in encoding["event_id"]


# ---------------------------------------------------------------------------
# Zarr: write / read roundtrip
# ---------------------------------------------------------------------------

def test_zarr_roundtrip(tmp_path, simple_dataset):
    """write_zarr then read_zarr preserves structure, dtypes, and values."""
    from ss_fha.io.zarr_io import read_zarr, write_zarr

    zarr_path = tmp_path / "test.zarr"
    write_zarr(simple_dataset, zarr_path, encoding=None, overwrite=False)

    ds_loaded = read_zarr(zarr_path, chunks=None)

    assert set(ds_loaded.data_vars) == set(simple_dataset.data_vars)
    np.testing.assert_array_equal(
        ds_loaded["flood_depth"].values,
        simple_dataset["flood_depth"].values,
    )
    np.testing.assert_array_equal(
        ds_loaded["event_id"].values,
        simple_dataset["event_id"].values,
    )


def test_zarr_roundtrip_preserves_coords(tmp_path, simple_dataset):
    """Zarr roundtrip preserves coordinate values."""
    from ss_fha.io.zarr_io import read_zarr, write_zarr

    zarr_path = tmp_path / "coords.zarr"
    write_zarr(simple_dataset, zarr_path, encoding=None, overwrite=False)
    ds_loaded = read_zarr(zarr_path, chunks=None)

    np.testing.assert_array_equal(ds_loaded.x.values, simple_dataset.x.values)
    np.testing.assert_array_equal(ds_loaded.y.values, simple_dataset.y.values)


# ---------------------------------------------------------------------------
# Zarr: overwrite protection
# ---------------------------------------------------------------------------

def test_zarr_overwrite_raises(tmp_path, simple_dataset):
    """write_zarr raises DataError when path exists and overwrite=False."""
    from ss_fha.exceptions import DataError
    from ss_fha.io.zarr_io import write_zarr

    zarr_path = tmp_path / "overwrite_test.zarr"
    write_zarr(simple_dataset, zarr_path, encoding=None, overwrite=False)

    with pytest.raises(DataError) as exc_info:
        write_zarr(simple_dataset, zarr_path, encoding=None, overwrite=False)

    assert "overwrite" in str(exc_info.value).lower()


def test_zarr_overwrite_true_replaces(tmp_path, simple_dataset):
    """write_zarr with overwrite=True silently replaces the existing store."""
    from ss_fha.io.zarr_io import read_zarr, write_zarr

    zarr_path = tmp_path / "replace.zarr"
    write_zarr(simple_dataset, zarr_path, encoding=None, overwrite=False)
    # Second write with overwrite=True must not raise
    write_zarr(simple_dataset, zarr_path, encoding=None, overwrite=True)

    ds_loaded = read_zarr(zarr_path, chunks=None)
    assert set(ds_loaded.data_vars) == set(simple_dataset.data_vars)


# ---------------------------------------------------------------------------
# Zarr: read missing path raises
# ---------------------------------------------------------------------------

def test_read_zarr_missing_path_raises(tmp_path):
    """read_zarr raises DataError when path does not exist."""
    from ss_fha.exceptions import DataError
    from ss_fha.io.zarr_io import read_zarr

    with pytest.raises(DataError):
        read_zarr(tmp_path / "nonexistent.zarr", chunks=None)


# ---------------------------------------------------------------------------
# Zarr: delete
# ---------------------------------------------------------------------------

def test_delete_zarr_removes_directory(tmp_path, simple_dataset):
    """delete_zarr removes an existing zarr store."""
    from ss_fha.io.zarr_io import delete_zarr, write_zarr

    zarr_path = tmp_path / "to_delete.zarr"
    write_zarr(simple_dataset, zarr_path, encoding=None, overwrite=False)
    assert zarr_path.exists()

    delete_zarr(zarr_path, timeout_s=10)
    assert not zarr_path.exists()


def test_delete_zarr_nonexistent_is_noop(tmp_path):
    """delete_zarr on a non-existent path does nothing (no error)."""
    from ss_fha.io.zarr_io import delete_zarr

    delete_zarr(tmp_path / "ghost.zarr", timeout_s=5)  # should not raise


# ---------------------------------------------------------------------------
# NetCDF: write / read roundtrip
# ---------------------------------------------------------------------------

def test_netcdf_roundtrip(tmp_path, simple_dataset):
    """write_compressed_netcdf then read_netcdf preserves values."""
    from ss_fha.io.netcdf_io import read_netcdf, write_compressed_netcdf

    nc_path = tmp_path / "test.nc"
    write_compressed_netcdf(simple_dataset, nc_path, encoding=None)

    ds_loaded = read_netcdf(nc_path)

    assert set(ds_loaded.data_vars) == set(simple_dataset.data_vars)
    np.testing.assert_array_almost_equal(
        ds_loaded["flood_depth"].values,
        simple_dataset["flood_depth"].values,
        decimal=5,
    )
    np.testing.assert_array_equal(
        ds_loaded["event_id"].values,
        simple_dataset["event_id"].values,
    )


def test_read_netcdf_missing_path_raises(tmp_path):
    """read_netcdf raises DataError when path does not exist."""
    from ss_fha.exceptions import DataError
    from ss_fha.io.netcdf_io import read_netcdf

    with pytest.raises(DataError):
        read_netcdf(tmp_path / "nonexistent.nc")


# ---------------------------------------------------------------------------
# GIS: load_geospatial_data_from_file
# ---------------------------------------------------------------------------

def test_load_geospatial_data_from_file(watershed_shapefile):
    """load_geospatial_data_from_file loads a shapefile into a GeoDataFrame."""
    pytest.importorskip("geopandas")
    import geopandas as gpd

    from ss_fha.io.gis_io import load_geospatial_data_from_file

    shp_path, _ = watershed_shapefile
    gdf = load_geospatial_data_from_file(shp_path, clip_to=None)

    assert isinstance(gdf, gpd.GeoDataFrame)
    assert len(gdf) == 1


def test_load_geospatial_data_from_file_missing_path_raises(tmp_path):
    """load_geospatial_data_from_file raises DataError when path does not exist."""
    from ss_fha.exceptions import DataError
    from ss_fha.io.gis_io import load_geospatial_data_from_file

    with pytest.raises(DataError):
        load_geospatial_data_from_file(tmp_path / "nonexistent.shp", clip_to=None)


def test_load_geospatial_data_from_file_unsupported_extension_raises(tmp_path):
    """load_geospatial_data_from_file raises DataError for unsupported extension."""
    from ss_fha.exceptions import DataError
    from ss_fha.io.gis_io import load_geospatial_data_from_file

    bad_path = tmp_path / "data.kml"
    bad_path.touch()  # file must exist to pass the extension check first

    with pytest.raises(DataError, match="Unsupported file extension"):
        load_geospatial_data_from_file(bad_path, clip_to=None)


def test_load_geospatial_data_from_file_clip_to(tmp_path, reference_ds_with_crs):
    """load_geospatial_data_from_file with clip_to clips to the bounding geometry."""
    pytest.importorskip("geopandas")
    pytest.importorskip("shapely")
    import geopandas as gpd
    from shapely.geometry import box

    from ss_fha.io.gis_io import load_geospatial_data_from_file

    ds = reference_ds_with_crs
    xmin, xmax = float(ds.x.min()), float(ds.x.max())
    ymin, ymax = float(ds.y.min()), float(ds.y.max())

    # Two polygons: one inside, one far outside
    poly_in = box(xmin, ymin, xmax, ymax)
    poly_out = box(xmin + 1e6, ymin + 1e6, xmax + 1e6, ymax + 1e6)
    gdf_all = gpd.GeoDataFrame(
        {"geometry": [poly_in, poly_out]}, crs="EPSG:32147"
    )

    shp_path = tmp_path / "two_polys.shp"
    gdf_all.to_file(shp_path)

    clip_poly = box(xmin - 10, ymin - 10, xmax + 10, ymax + 10)
    clip_gdf = gpd.GeoDataFrame({"geometry": [clip_poly]}, crs="EPSG:32147")

    result = load_geospatial_data_from_file(shp_path, clip_to=clip_gdf)
    assert len(result) == 1  # only the inside polygon survives


# ---------------------------------------------------------------------------
# GIS: create_mask_from_polygon — file path input
# ---------------------------------------------------------------------------

def test_create_mask_from_polygon_filepath(watershed_shapefile, reference_ds_with_crs):
    """create_mask_from_polygon with a file path produces a boolean DataArray."""
    pytest.importorskip("rioxarray")
    import xarray as xr

    from ss_fha.io.gis_io import create_mask_from_polygon

    shp_path, _ = watershed_shapefile
    mask = create_mask_from_polygon(
        polygon=shp_path,
        reference_ds=reference_ds_with_crs,
        crs_epsg=32147,
    )

    assert isinstance(mask, xr.DataArray)
    assert mask.dtype == bool
    assert set(mask.dims) == {"x", "y"}


def test_create_mask_from_polygon_full_coverage_filepath(
    watershed_shapefile, reference_ds_with_crs
):
    """File-path polygon covering entire grid produces an all-True mask."""
    pytest.importorskip("rioxarray")

    from ss_fha.io.gis_io import create_mask_from_polygon

    shp_path, _ = watershed_shapefile
    mask = create_mask_from_polygon(
        polygon=shp_path,
        reference_ds=reference_ds_with_crs,
        crs_epsg=32147,
    )

    assert mask.values.all(), "Expected all cells True (polygon covers full grid)"


def test_create_mask_from_polygon_geodataframe(
    watershed_shapefile, reference_ds_with_crs
):
    """create_mask_from_polygon with a GeoDataFrame produces a boolean DataArray."""
    pytest.importorskip("rioxarray")
    import xarray as xr

    from ss_fha.io.gis_io import create_mask_from_polygon, load_geospatial_data_from_file

    shp_path, _ = watershed_shapefile
    gdf = load_geospatial_data_from_file(shp_path, clip_to=None)

    mask = create_mask_from_polygon(
        polygon=gdf,
        reference_ds=reference_ds_with_crs,
        crs_epsg=32147,
    )

    assert isinstance(mask, xr.DataArray)
    assert mask.dtype == bool
    assert mask.values.all()


def test_create_mask_from_polygon_geoseries(
    watershed_shapefile, reference_ds_with_crs
):
    """create_mask_from_polygon with a GeoSeries produces a boolean DataArray."""
    pytest.importorskip("rioxarray")
    import xarray as xr

    from ss_fha.io.gis_io import create_mask_from_polygon, load_geospatial_data_from_file

    shp_path, _ = watershed_shapefile
    gdf = load_geospatial_data_from_file(shp_path, clip_to=None)

    mask = create_mask_from_polygon(
        polygon=gdf.geometry,
        reference_ds=reference_ds_with_crs,
        crs_epsg=32147,
    )

    assert isinstance(mask, xr.DataArray)
    assert mask.dtype == bool
    assert mask.values.all()


def test_create_mask_from_polygon_shapely_geometry(
    watershed_shapefile, reference_ds_with_crs
):
    """create_mask_from_polygon with a bare Shapely geometry produces a boolean DataArray."""
    pytest.importorskip("rioxarray")
    import xarray as xr

    from ss_fha.io.gis_io import create_mask_from_polygon, load_geospatial_data_from_file

    shp_path, _ = watershed_shapefile
    gdf = load_geospatial_data_from_file(shp_path, clip_to=None)
    # Bare geometry has no CRS — caller must ensure it matches crs_epsg
    geom = gdf.geometry.iloc[0]

    mask = create_mask_from_polygon(
        polygon=geom,
        reference_ds=reference_ds_with_crs,
        crs_epsg=32147,
    )

    assert isinstance(mask, xr.DataArray)
    assert mask.dtype == bool
    assert mask.values.all()


def test_create_mask_from_polygon_missing_file_raises(
    tmp_path, reference_ds_with_crs
):
    """create_mask_from_polygon raises DataError when file path does not exist."""
    from ss_fha.exceptions import DataError
    from ss_fha.io.gis_io import create_mask_from_polygon

    with pytest.raises(DataError):
        create_mask_from_polygon(
            polygon=tmp_path / "ghost.shp",
            reference_ds=reference_ds_with_crs,
            crs_epsg=32147,
        )


def test_create_mask_from_polygon_unsupported_type_raises(
    reference_ds_with_crs,
):
    """create_mask_from_polygon raises DataError for unsupported input type."""
    from ss_fha.exceptions import DataError
    from ss_fha.io.gis_io import create_mask_from_polygon

    with pytest.raises(DataError, match="Unsupported polygon input type"):
        create_mask_from_polygon(
            polygon=42,  # type: ignore[arg-type]
            reference_ds=reference_ds_with_crs,
            crs_epsg=32147,
        )


def test_create_mask_from_polygon_missing_spatial_coord_raises(
    watershed_shapefile, simple_dataset
):
    """create_mask_from_polygon raises DataError if reference_ds lacks x/y."""
    pytest.importorskip("rioxarray")
    from ss_fha.exceptions import DataError
    from ss_fha.io.gis_io import create_mask_from_polygon

    shp_path, _ = watershed_shapefile
    ds_no_x = simple_dataset.drop_vars("x")

    with pytest.raises(DataError):
        create_mask_from_polygon(
            polygon=shp_path,
            reference_ds=ds_no_x,
            crs_epsg=32147,
        )


# ---------------------------------------------------------------------------
# GIS: rasterize_features
# ---------------------------------------------------------------------------

def test_rasterize_features_sequential_ids(
    watershed_shapefile, reference_ds_with_crs
):
    """rasterize_features with field=None assigns sequential 1-based IDs."""
    pytest.importorskip("rioxarray")
    import xarray as xr

    from ss_fha.io.gis_io import load_geospatial_data_from_file, rasterize_features

    shp_path, _ = watershed_shapefile
    gdf = load_geospatial_data_from_file(shp_path, clip_to=None)

    result = rasterize_features(gdf, reference_ds_with_crs, field=None)

    assert isinstance(result, xr.DataArray)
    # The polygon covers the whole grid so all cells should be 1 (first feature)
    covered = result.values[result.values != -9999]
    assert set(covered) == {1}


def test_rasterize_features_bad_field_raises(
    watershed_shapefile, reference_ds_with_crs
):
    """rasterize_features raises DataError when field not in GeoDataFrame."""
    pytest.importorskip("rioxarray")
    from ss_fha.exceptions import DataError
    from ss_fha.io.gis_io import load_geospatial_data_from_file, rasterize_features

    shp_path, _ = watershed_shapefile
    gdf = load_geospatial_data_from_file(shp_path, clip_to=None)

    with pytest.raises(DataError):
        rasterize_features(gdf, reference_ds_with_crs, field="nonexistent_col")
