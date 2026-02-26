"""I/O layer for ss-fha.

Provides thin, purpose-built functions for reading and writing zarr, NetCDF,
and GIS data. No computation logic lives here — each function has one job.

All functions raise `ss_fha.exceptions.DataError` on failure.
"""

from ss_fha.io.gis_io import (
    create_mask_from_shapefile,
    rasterize_features,
    read_shapefile,
)
from ss_fha.io.netcdf_io import read_netcdf, write_compressed_netcdf
from ss_fha.io.zarr_io import (
    default_zarr_encoding,
    delete_zarr,
    read_zarr,
    write_zarr,
)

__all__ = [
    "write_zarr",
    "read_zarr",
    "delete_zarr",
    "default_zarr_encoding",
    "write_compressed_netcdf",
    "read_netcdf",
    "read_shapefile",
    "create_mask_from_shapefile",
    "rasterize_features",
]
