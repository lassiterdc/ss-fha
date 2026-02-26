"""NetCDF read/write utilities for ss-fha.

All functions wrap xarray operations and raise `ss_fha.exceptions.DataError`
on failure. No raw I/O exceptions escape.

Design notes
------------
- `compression_level: int = 5` is the only argument with a default. Five is a
  widely accepted middle-ground for zlib. Callers may override explicitly.
- `encoding=None` is a sentinel meaning "compute automatically". Callers may
  supply their own encoding dict.
- The h5netcdf engine is used for writing because it supports chunked writes
  via dask; the scipy engine forces full in-memory materialization.
"""

from __future__ import annotations

from pathlib import Path

import xarray as xr

from ss_fha.exceptions import DataError


def _default_netcdf_encoding(ds: xr.Dataset, compression_level: int) -> dict:
    """Build a zlib encoding dictionary for all numeric variables.

    Internal helper — callers use ``write_compressed_netcdf`` directly.
    """
    encoding: dict = {}
    for var in ds.data_vars:
        if ds[var].dtype.kind in {"i", "u", "f"}:
            encoding[var] = {
                "zlib": True,
                "complevel": compression_level,
                "shuffle": True,
            }
    return encoding


def write_compressed_netcdf(
    ds: xr.Dataset,
    path: Path,
    encoding: dict | None,
    compression_level: int = 5,
) -> None:
    """Write an xarray Dataset to a compressed NetCDF4 file.

    Parameters
    ----------
    ds:
        Dataset to write.
    path:
        Destination file path (should end in ``.nc`` or ``.netcdf``).
    encoding:
        NetCDF encoding dict. Pass ``None`` to use zlib compression at
        ``compression_level`` for all numeric variables.
    compression_level:
        zlib compression level (1–9). Default 5. Used only when
        ``encoding=None``.

    Raises
    ------
    DataError
        If the write fails for any reason.
    """
    path = Path(path)

    if encoding is None:
        encoding = _default_netcdf_encoding(ds, compression_level)

    try:
        ds.to_netcdf(path, encoding=encoding, engine="h5netcdf")
    except Exception as e:
        raise DataError(
            operation="write compressed netcdf",
            filepath=path,
            reason=str(e),
        ) from e


def read_netcdf(path: Path) -> xr.Dataset:
    """Open a NetCDF file as an xarray Dataset.

    Parameters
    ----------
    path:
        Path to the NetCDF file.

    Returns
    -------
    xr.Dataset

    Raises
    ------
    DataError
        If the path does not exist or the file cannot be opened.
    """
    path = Path(path)

    if not path.exists():
        raise DataError(
            operation="read netcdf",
            filepath=path,
            reason="Path does not exist.",
        )

    try:
        return xr.open_dataset(path)
    except Exception as e:
        raise DataError(
            operation="read netcdf",
            filepath=path,
            reason=str(e),
        ) from e
