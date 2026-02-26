# Utility Package Candidates

This file tracks functions and classes that are project-agnostic — useful beyond both `ss_fha` and `TRITON-SWMM_toolkit` — and are candidates for extraction into a shared, pip-installable utility package.

**Why maintain this list?**
Generic utilities extracted into a separate package can be reused across projects without copy-pasting, versioned independently, and contributed back to the community. Even a small internal package avoids the "copy from TRITON-SWMM_toolkit" anti-pattern.

**How to add a candidate:**
When you write or port a function that has no domain-specific logic (no flood, no hydrology, no SWMM), add it here with a brief note on why it is generic.

**Threshold for adding:** Would a Python developer working on a completely different scientific computing project plausibly want this? If yes, it's a candidate.

---

## Candidates

| Function / Class | Current Location | Why Generic | Notes |
|-----------------|-----------------|-------------|-------|
| `WorkflowError._indent(text, prefix)` | `src/ss_fha/exceptions.py` | Pure string utility: indents each line of a multi-line string by a prefix. No domain logic. | Currently a private static method on `WorkflowError`; could be a standalone `indent_text()` function |
| `write_zarr(ds, path, encoding, overwrite, compression_level)` | `src/ss_fha/io/zarr_io.py` (planned) | xarray-to-zarr with Blosc encoding, overwrite protection, and `DataError` wrapping. Any scientific Python project using zarr needs this. | Analogous to `TRITON_SWMM_toolkit.utils.write_zarr`; written fresh because toolkit version has default args and no `DataError` wrapping |
| `read_zarr(path, chunks)` | `src/ss_fha/io/zarr_io.py` (planned) | Generic zarr-to-xarray loader with `DataError` wrapping on failure. | No direct analogue in TRITON-SWMM_toolkit (toolkit reads inline); written fresh |
| `delete_zarr(path, timeout_s)` | `src/ss_fha/io/zarr_io.py` (planned) | Zarr directory deletion with polling retry and timeout. Useful for any workflow that overwrites zarr outputs. | Analogous to `TRITON_SWMM_toolkit.utils` `delete_zarr` / `fast_rmtree`; written fresh for `DataError` and explicit signature |
| `default_zarr_encoding(ds, compression_level)` | `src/ss_fha/io/zarr_io.py` (planned) | Builds Blosc/zstd encoding dict for all numeric variables in an xarray Dataset. | Analogous to `TRITON_SWMM_toolkit.utils.return_dic_zarr_encodings`; written fresh for explicit `compression_level` argument |
| `write_compressed_netcdf(ds, path, compression_level, encoding)` | `src/ss_fha/io/netcdf_io.py` (planned) | xarray-to-netcdf with zlib compression and `DataError` wrapping. | Analogous to `TRITON_SWMM_toolkit.utils.write_netcdf`; written fresh for explicit args and error handling |
| `read_netcdf(path)` | `src/ss_fha/io/netcdf_io.py` (planned) | Generic netcdf-to-xarray loader with `DataError` wrapping. | No direct analogue in toolkit; written fresh |

---

## Patterns to Watch For

- Deferred validation (`ValidationResult` + `ValidationIssue` accumulator pattern) — useful in any CLI tool with complex config
- Log-based completion checks for subprocess runners — useful in any Snakemake project
- BagIt checksum validation for HydroShare downloads — useful in any HydroShare-backed project
- Platform detection helpers (`uses_slurm()`, `on_uva_hpc()`) — useful in any HPC workflow project

---

## Potential Package Names

- `hydro-utils` — domain-scoped but broad
- `scientific-workflow-utils` — very broad
- `snakemake-scientific-utils` — Snakemake-specific utilities

No decision needed yet. The list should grow organically before a package name is chosen.
