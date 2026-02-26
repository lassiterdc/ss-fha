"""Generic xarray utilities for ss-fha.

Functions here have no flood-domain logic and are candidates for extraction
into a shared utility package (see docs/planning/utility_package_candidates.md).
"""

import xarray as xr


def sort_dimensions(ds: xr.Dataset, dims: list[str]) -> xr.Dataset:
    """Sort a Dataset along each specified dimension.

    Parameters
    ----------
    ds:
        Dataset to sort.
    dims:
        Ordered list of dimension names to sort by. Each dimension is sorted
        in ascending order using its coordinate values.

    Returns
    -------
    xr.Dataset
        Dataset sorted along all specified dimensions.
    """
    for dim in dims:
        ds = ds.sortby(variables=dim)
    return ds
