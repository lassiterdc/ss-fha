# Work Chunk 01D: I/O Layer

**Phase**: 1D — Foundation (I/O Layer)
**Last edited**: 2026-02-25

---

## Before Proceeding

Review the following documents before making any edits to plans or writing any code:

- [`docs/planning/active/refactors/full_codebase_refactor/full_codebase_refactor.md`](../full_codebase_refactor.md) — master refactor plan; update it if any decisions made here affect the overall plan.
- [`CONTRIBUTING.md`](../../../../CONTRIBUTING.md) — project development philosophy; all implementation decisions must align with it.

**Prerequisite**: Work chunks 01A–01C complete (exceptions, defaults, config model, paths all importable).

---

## Task Understanding

### Requirements

Create a clean I/O layer that separates data loading/writing from computation. All data access in the pipeline goes through this layer. No computation module should contain raw `xr.open_zarr()` or `gpd.read_file()` calls — they call these I/O functions instead.

**Before writing any code**, check `/home/dcl3nd/dev/TRITON-SWMM_toolkit/src/TRITON_SWMM_toolkit/` for reusable I/O utilities (zarr read/write, netcdf, gis). If functions can be imported directly, do so rather than duplicating.

**Modules to create:**

1. `src/ss_fha/io/__init__.py`
2. `src/ss_fha/io/zarr_io.py`:
   - `write_zarr(ds: xr.Dataset, path: Path, encoding: dict | None, overwrite: bool) -> None`
   - `read_zarr(path: Path, chunks: dict | None) -> xr.Dataset`
   - `delete_zarr(path: Path, timeout_s: int) -> None`
   - `default_zarr_encoding(ds: xr.Dataset) -> dict`
3. `src/ss_fha/io/netcdf_io.py`:
   - `write_compressed_netcdf(ds: xr.Dataset, path: Path, encoding: dict | None) -> None`
   - `read_netcdf(path: Path) -> xr.Dataset`
4. `src/ss_fha/io/gis_io.py`:
   - `read_shapefile(path: Path) -> gpd.GeoDataFrame`
   - `create_mask_from_shapefile(shapefile_path: Path, reference_ds: xr.Dataset, crs_epsg: int) -> xr.DataArray`
   - `rasterize_features(gdf: gpd.GeoDataFrame, reference_ds: xr.Dataset, field: str | None) -> xr.DataArray`

### Key Design Decisions

- **No defaults on arguments** (per philosophy.md) — except where a `None` means "compute automatically" (e.g., `encoding=None` means `default_zarr_encoding` is called internally), or where a default is widely accepted and rarely overridden.
- **`compression_level: int = 5`** is a documented exception to the no-defaults rule. A value of 5 is a reasonable middle-ground for both zstd (zarr) and zlib (netcdf) compression. Callers may override it explicitly; it should also be settable via YAML config in a future config model extension.
- All functions raise `ss_fha.exceptions.DataError` on failure, not raw I/O exceptions — wrap file operations in try/except and re-raise with context (operation, filepath, reason).
- `overwrite=False` in `write_zarr` raises `DataError` if path exists — no silent overwrites.
- `crs_epsg` in `create_mask_from_shapefile` is a required argument, not a default.
- **Geospatial files are raw / unclipped** (decided in work chunk 00, Decision 1): the HydroShare staging directory holds raw city-wide or statewide shapefiles (roads, buildings, sidewalks). The I/O layer is responsible for clipping to the watershed polygon on load. `read_shapefile` must accept a `clip_to: gpd.GeoDataFrame | None` argument — this is not optional syntactically, but callers pass `None` when no clipping is needed (e.g., the watershed shapefile itself). Per philosophy.md, no silent default: callers must be explicit. If clipping is computationally expensive for large files (e.g., Virginia statewide buildings shapefile), the clip result should be saved to `output_dir/preprocessed/` and referenced by a dedicated Snakemake pre-processing rule that downstream rules depend on.
- **Integer variable names in time series NetCDFs** (`156`, `171`, `170`, `155`, `140`, `141`): These are SWMM subcatchment IDs with assigned rainfall time series. They are not used by the ss-fha library. The domain-wide average rainfall intensity variable `mm_per_hr` is what ss-fha uses for rain event statistics and return period calculations. No special handling is needed in the generic `read_netcdf()` function.
- **TRITON-SWMM_toolkit I/O functions** (`write_zarr`, `write_netcdf`, `return_dic_zarr_encodings`, `create_mask_from_shapefile` in `TRITON_SWMM_toolkit.utils`) are analogous to functions implemented here but violate this project's design philosophy (default arguments, no `DataError` wrapping, differing signatures). Per philosophy.md, fresh implementations are written for ss-fha, and each is noted in `docs/planning/utility_package_candidates.md` with its toolkit analogue.

### Success Criteria

- Zarr roundtrip (write → read) preserves dataset structure, dtypes, and values
- NetCDF roundtrip works with compression
- Shapefile masking produces correct boolean DataArray against synthetic geometries
- All tests in `tests/test_io.py` pass

---

## Evidence from Codebase

Before implementing, inspect:

1. `/home/dcl3nd/dev/TRITON-SWMM_toolkit/src/TRITON_SWMM_toolkit/` — search for zarr, netcdf, gis I/O functions to import or reference
2. `_old_code_to_refactor/__utils.py` — identify I/O functions to extract (zarr read/write, mask creation, rasterization)
3. `src/ss_fha/exceptions.py` (from 01A) — use `DataError`

---

## Implementation Strategy

### Chosen Approach

Write thin, purpose-built I/O functions that wrap xarray, zarr, geopandas, and rasterio. Each function has one job: read or write one data type. No computation logic inside I/O functions.

TRITON-SWMM_toolkit has analogous I/O utilities, but they violate this project's design philosophy (default arguments, no `DataError` wrapping). Fresh ss-fha implementations were written instead, with each documented in `docs/planning/utility_package_candidates.md` alongside its toolkit analogue.

### Alternatives Considered

- **Put I/O in core modules**: Rejected — makes unit testing impossible without real data files.
- **Class-based I/O manager**: Rejected — functions are simpler and sufficient; a class would add indirection without benefit.

### Trade-offs

- Thin I/O functions mean callers must handle chunking strategy — this is correct because chunking is analysis-specific.

---

## File-by-File Change Plan

### New Files

| File | Purpose |
|------|---------|
| `src/ss_fha/io/__init__.py` | Package stub; re-export key I/O functions |
| `src/ss_fha/io/zarr_io.py` | Zarr read/write/delete + encoding |
| `src/ss_fha/io/netcdf_io.py` | NetCDF read/write with compression |
| `src/ss_fha/io/gis_io.py` | Shapefile read, masking, rasterization |
| `tests/test_io.py` | I/O roundtrip and masking tests |

### Modified Files

| File | Change |
|------|--------|
| `_old_code_to_refactor/__utils.py` | Add/update refactoring status block for I/O functions |

---

## Risks and Edge Cases

| Risk | Mitigation |
|------|-----------|
| Zarr v2 vs v3 format differences | Zarr V3 specification warnings suppressed via `warnings.filterwarnings` in `write_zarr`; `consolidated=False` used on read/write |
| `delete_zarr` with timeout: directory may be locked by another process | Use polling loop with `timeout_s`; raise `DataError` on timeout |
| CRS mismatch between shapefile and reference dataset | Re-project shapefile to `crs_epsg` inside `create_mask_from_shapefile` before masking |
| Rasterization requires matching resolution/extent | Validate reference_ds has spatial coordinates before rasterizing; raise `DataError` if not |

---

## Validation Plan

```bash
# Zarr roundtrip
pytest tests/test_io.py::test_zarr_roundtrip -v

# NetCDF roundtrip
pytest tests/test_io.py::test_netcdf_roundtrip -v

# Zarr encoding structure
pytest tests/test_io.py::test_zarr_encoding_defaults -v

# Overwrite protection
pytest tests/test_io.py::test_zarr_overwrite_raises -v

# GIS masking (synthetic geometry)
pytest tests/test_io.py::test_create_mask_from_shapefile -v

# Full test suite
pytest tests/test_io.py -v
```

---

## Documentation and Tracker Updates

- Add/update refactoring status block in `_old_code_to_refactor/__utils.py` for all migrated I/O functions.
- Update `full_codebase_refactor.md` tracking table: `__utils.py` — note I/O functions migrated.

---

## Definition of Done

- [x] `src/ss_fha/io/zarr_io.py` implemented with all four functions
- [x] `src/ss_fha/io/netcdf_io.py` implemented
- [x] `src/ss_fha/io/gis_io.py` implemented
- [x] All functions raise `DataError` (not raw I/O exceptions) on failure
- [x] `crs_epsg` is a required argument in `create_mask_from_shapefile` (no default)
- [x] All `tests/test_io.py` tests pass with synthetic data (21/21)
- [x] Refactoring status block updated in `_old_code_to_refactor/__utils.py`
- [x] `full_codebase_refactor.md` tracking table updated
- [x] New I/O functions added to `docs/planning/utility_package_candidates.md` with TRITON-SWMM_toolkit analogues noted
- [x] **Moved to `implemented/` 2026-02-25**
