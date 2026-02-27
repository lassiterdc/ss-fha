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
| `uses_slurm() -> bool` | `tests/utils_for_testing.py` | Checks for `sbatch` on PATH — correctly detects SLURM availability from a login node, not just inside a running job. Useful in any HPC workflow test suite. | TRITON-SWMM_toolkit version checks `SLURM_JOB_ID` env var (incorrect for login-node use); ss-fha version uses `shutil.which("sbatch")` |
| `sort_dimensions(ds, dims)` | `src/ss_fha/core/utils.py` | Sorts an xarray Dataset along a list of named dimensions. No domain logic whatsoever — useful in any xarray workflow. | No direct analogue in TRITON-SWMM_toolkit; written fresh with required (non-default) `dims` argument per ss-fha philosophy |
| `ComputationError(message)` | `src/ss_fha/exceptions.py` | Exception for pure-computation failures with no associated file path (bad data shape, unexpected NaN, failed column lookup). No domain logic. Generic complement to `DataError` for workflows that separate I/O from computation. | Distinct from `DataError(operation, filepath, reason)` — use `ComputationError` when no file is involved |
| `empirical_multivariate_return_periods(df_samples, n_years, alpha, beta)` | `src/ss_fha/core/event_statistics.py` | Vectorized numpy broadcast implementation of empirical AND/OR multivariate return periods. ~50–200× faster than apply-based equivalent (O(n²) Python loop → single broadcast op). No flood, hydrology, or SWMM domain logic. | Also includes `_empirical_multivariate_return_periods_reference` (apply-based reference) for validation. Other statistical methods in `event_statistics.py` with no flood-domain logic (empirical CDF plotting position computation, univariate return period computation) are also likely candidates as the module matures. |
| `grid_cell_size_m(ds)` | `src/ss_fha/core/geospatial.py` | Returns the cell size of a regular spatial grid (xarray Dataset or DataArray with `x`/`y` coords) using mode of first-differences — robust to floating-point noise. Raises if x and y cell sizes differ (fail-fast for non-square grids). Zero flood/hydrology domain logic. | Works on any CF-convention xarray grid. Name includes `_m` (metres) only because that is what the caller's grid uses; the implementation itself is unit-agnostic. |
| `calculate_positions(data, alpha, beta, fillna_val)` | `src/ss_fha/core/empirical_frequency_analysis.py` | Computes empirical CDF plotting positions for any 1-D numeric array via the generalized Hazen family formula. Delegates to `scipy.stats.mstats.plotting_positions`. NaN filling and post-fill max-assignment are the only project-specific choices, and both are controlled by the caller via `fillna_val`. No flood/hydrology domain logic. | Moved from `flood_probability.py` in Work Chunk 02E. The Hazen family (Weibull, Cunnane, Gringorten, Blom) is standard in hydrology and statistics generally. |
| `calculate_return_period(positions, n_years, n_events)` | `src/ss_fha/core/empirical_frequency_analysis.py` | Converts empirical CDF plotting positions to return periods using `T = 1 / ((1 - F) * lambda)` where `lambda = n_events / n_years`. Purely arithmetic. No flood/hydrology domain logic. | Moved from `flood_probability.py` in Work Chunk 02E. Generic enough for any recurrence-interval analysis (storms, earthquakes, financial events). |
| `compute_return_periods_for_series(s, n_years, alpha, beta, assign_dup_vals_max_return)` | `src/ss_fha/core/empirical_frequency_analysis.py` | Sorts a `pd.Series`, calls `calculate_positions` + `calculate_return_period`, and assembles an output DataFrame with empirical CDF and return period columns. Duplicate-value handling is controlled by the explicit `assign_dup_vals_max_return` argument. No flood/hydrology domain logic. | Moved from `event_statistics.py` (was `_compute_return_periods_for_series`) in Work Chunk 02E. Useful for any time-series or event-frequency analysis workflow. |

---

## Patterns to Watch For

- `ValidationResult` + `ValidationIssue` accumulator pattern (`ss_fha/validation.py`) — useful in any CLI tool or scientific workflow with complex multi-field config. ss-fha's version diverges from `TRITON_SWMM_toolkit.validation` by: (1) omitting the ERROR/WARNING severity split (all issues are blocking), (2) requiring a non-empty `fix_hint` on every issue, and (3) raising `SSFHAValidationError(issues: list[str])` instead of `ConfigurationError`. Consolidating both into a shared package would require reconciling these design choices.
- Log-based completion checks for subprocess runners — useful in any Snakemake project
- BagIt checksum validation for HydroShare downloads — useful in any HydroShare-backed project
- Platform detection helpers (`uses_slurm()`) — now tracked in the candidates table above

---

## Potential Package Names

- `hydro-utils` — domain-scoped but broad
- `scientific-workflow-utils` — very broad
- `snakemake-scientific-utils` — Snakemake-specific utilities

No decision needed yet. The list should grow organically before a package name is chosen.
