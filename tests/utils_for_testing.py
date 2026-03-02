"""Platform detection and assertion helpers for ss-fha tests.

Analogues to TRITON-SWMM_toolkit/tests/utils_for_testing.py — candidates
for consolidation into a shared utility package (see
docs/planning/utility_package_candidates.md).
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
import xarray as xr

# ---------------------------------------------------------------------------
# Platform detection
# ---------------------------------------------------------------------------


def uses_slurm() -> bool:
    """Return True when running on a system where SLURM is available.

    Checks for the presence of ``sbatch`` on PATH, which is true on any
    SLURM-based login node or compute node. This is the correct signal for
    gating tests that submit SLURM jobs — ``SLURM_JOB_ID`` is only set
    inside a running job, not on a login node.
    """
    return shutil.which("sbatch") is not None


# ---------------------------------------------------------------------------
# Pytest skip marks
# ---------------------------------------------------------------------------

skip_if_no_slurm = pytest.mark.skipif(
    not uses_slurm(),
    reason="Requires a SLURM-capable system (sbatch not found on PATH).",
)

skip_if_no_hydroshare = pytest.mark.skipif(
    True,
    reason=("HydroShare integration not yet implemented. Deferred to HPC implementation phase."),
)


# ---------------------------------------------------------------------------
# Assertion helpers
# ---------------------------------------------------------------------------


def assert_zarr_valid(path: Path, expected_vars: list[str] | None) -> None:
    """Assert that a zarr store exists and contains the expected variables.

    Raises ``DataError`` (via ``read_zarr``) if the store cannot be opened,
    and ``AssertionError`` if expected variables are missing.

    Parameters
    ----------
    path:
        Path to the zarr directory to validate.
    expected_vars:
        List of data variable names that must be present in the store.
        Pass ``None`` to skip variable name checks (existence check only).
    """
    from ss_fha.io.zarr_io import read_zarr

    ds = read_zarr(path=path, chunks=None)

    if expected_vars is not None:
        missing = [v for v in expected_vars if v not in ds.data_vars]
        if missing:
            raise AssertionError(
                f"zarr store at {path} is missing expected variables: {missing}. "
                f"Present variables: {list(ds.data_vars)}"
            )

    ds.close()


def assert_flood_probs_valid(ds: xr.Dataset) -> None:
    """Assert that a flood probability Dataset has the expected structure.

    Checks for the presence of spatial coordinates and the flood
    probability variables produced by ``compute_emp_cdf_and_return_pds``:
    ``max_wlevel_m``, ``empirical_cdf``, and ``return_pd_yrs``.

    Parameters
    ----------
    ds:
        Dataset to validate (e.g., output of a flood probability computation).
    """
    spatial_coords = {"x", "y"}
    present_coords = set(ds.coords)

    missing_coords = spatial_coords - present_coords
    if missing_coords:
        raise AssertionError(
            f"Flood probability Dataset is missing spatial coordinates: "
            f"{missing_coords}. Present coords: {present_coords}"
        )

    expected_vars = {"max_wlevel_m", "empirical_cdf", "return_pd_yrs"}
    missing_vars = expected_vars - set(ds.data_vars)
    if missing_vars:
        raise AssertionError(
            f"Flood probability Dataset is missing expected variables: "
            f"{sorted(missing_vars)}. Present variables: {sorted(ds.data_vars)}"
        )
