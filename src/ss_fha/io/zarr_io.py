"""Zarr read/write/delete utilities for ss-fha.

All functions wrap xarray and zarr operations and raise
`ss_fha.exceptions.DataError` on failure. No raw I/O exceptions escape.

Design notes
------------
- `compression_level: int = 5` is the only argument with a default in this
  module. Five is a widely accepted middle-ground for zstd (fast decode, good
  ratio). Callers may override it explicitly.
- `overwrite=False` is a *required* argument; callers must be explicit about
  whether they intend to overwrite existing data.
- `encoding=None` is a sentinel meaning "compute automatically via
  `default_zarr_encoding`". Callers may supply their own encoding dict.
"""

from __future__ import annotations

import gc
import shutil
import time
from pathlib import Path

import xarray as xr

from ss_fha.exceptions import DataError


def default_zarr_encoding(ds: xr.Dataset, compression_level: int = 5) -> dict:
    """Build a Blosc/zstd encoding dictionary for all numeric variables.

    Numeric variables (int, uint, float) get Blosc/zstd compression at
    `compression_level`. String (Unicode) coordinates get a fixed-width dtype
    that preserves the longest string. Other types are left unencoded.

    Parameters
    ----------
    ds:
        Dataset whose variables and coordinates will be encoded.
    compression_level:
        Blosc compression level (1–9). Default 5 is a reasonable middle-ground.

    Returns
    -------
    dict
        Encoding dict suitable for ``ds.to_zarr(..., encoding=encoding)``.

    Raises
    ------
    DataError
        If the encoding dict cannot be constructed (e.g., zarr not installed).
    """
    try:
        import zarr

        compressor = zarr.codecs.BloscCodec(
            cname="zstd",
            clevel=compression_level,
            shuffle=zarr.codecs.BloscShuffle.shuffle,
        )

        encoding: dict = {}

        for var in ds.data_vars:
            if ds[var].dtype.kind in {"i", "u", "f"}:
                encoding[var] = {"compressors": compressor}

        for coord in ds.coords:
            if ds[coord].dtype.kind == "U":
                max_len = int(ds[coord].str.len().max().item())
                encoding[coord] = {"dtype": f"<U{max_len}"}

        return encoding

    except Exception as e:
        raise DataError(
            operation="build zarr encoding",
            filepath=Path("<no file>"),
            reason=str(e),
        ) from e


def write_zarr(
    ds: xr.Dataset,
    path: Path,
    encoding: dict | None,
    overwrite: bool,
    compression_level: int = 5,
) -> None:
    """Write an xarray Dataset to a zarr store.

    Parameters
    ----------
    ds:
        Dataset to write.
    path:
        Destination zarr directory path.
    encoding:
        Zarr encoding dict. Pass ``None`` to use ``default_zarr_encoding``
        with the given ``compression_level``.
    overwrite:
        If ``True``, delete the existing store before writing. If ``False``
        and the path already exists, raise ``DataError``.
    compression_level:
        Blosc compression level used when ``encoding=None``. Default 5.

    Raises
    ------
    DataError
        If ``overwrite=False`` and ``path`` exists, or if the write fails.
    """
    path = Path(path)

    if path.exists():
        if not overwrite:
            raise DataError(
                operation="write zarr",
                filepath=path,
                reason=(
                    "Path already exists and overwrite=False. "
                    "Pass overwrite=True to replace it."
                ),
            )
        delete_zarr(path, timeout_s=30)

    if encoding is None:
        encoding = default_zarr_encoding(ds, compression_level)

    try:
        import warnings

        with warnings.catch_warnings():
            warnings.filterwarnings(
                "ignore",
                message=".*does not have a Zarr V3 specification.*",
                category=Warning,
            )
            ds.to_zarr(path, mode="w", encoding=encoding, consolidated=False)
    except Exception as e:
        raise DataError(
            operation="write zarr",
            filepath=path,
            reason=str(e),
        ) from e


def read_zarr(path: Path, chunks: dict | None) -> xr.Dataset:
    """Open a zarr store as an xarray Dataset.

    Parameters
    ----------
    path:
        Path to the zarr directory.
    chunks:
        Dask chunk specification. Pass ``None`` to load eagerly (no dask).
        Pass a dict (e.g., ``{"x": 256, "y": 256}``) or ``"auto"`` string
        to load lazily with dask. Note: ``"auto"`` must be passed as a
        one-element dict ``{"x": "auto", ...}`` or the string ``"auto"``
        directly — xarray accepts both.

    Returns
    -------
    xr.Dataset

    Raises
    ------
    DataError
        If the path does not exist or the store cannot be opened.
    """
    path = Path(path)

    if not path.exists():
        raise DataError(
            operation="read zarr",
            filepath=path,
            reason="Path does not exist.",
        )

    try:
        return xr.open_dataset(
            path,
            engine="zarr",
            chunks=chunks,
            consolidated=False,
        )
    except Exception as e:
        raise DataError(
            operation="read zarr",
            filepath=path,
            reason=str(e),
        ) from e


def delete_zarr(path: Path, timeout_s: int) -> None:
    """Delete a zarr directory, retrying until timeout if the OS resists.

    On Windows (and occasionally on Linux with open dask file handles),
    ``shutil.rmtree`` can fail immediately after a computation finishes.
    This function polls until the directory is gone or ``timeout_s`` elapses.

    Parameters
    ----------
    path:
        Path to the zarr directory to delete.
    timeout_s:
        Maximum seconds to keep retrying before raising ``DataError``.

    Raises
    ------
    DataError
        If the directory still exists after ``timeout_s`` seconds.
    """
    path = Path(path)

    if not path.exists():
        return

    deadline = time.monotonic() + timeout_s
    last_exc: Exception | None = None

    while time.monotonic() < deadline:
        try:
            gc.collect()
            shutil.rmtree(path)
            if not path.exists():
                return
        except Exception as e:
            last_exc = e
            time.sleep(0.5)

    raise DataError(
        operation="delete zarr",
        filepath=path,
        reason=(
            f"Directory still exists after {timeout_s}s. "
            f"Last error: {last_exc}"
        ),
    )
