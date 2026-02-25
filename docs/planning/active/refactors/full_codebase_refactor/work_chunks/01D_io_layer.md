# Work Chunk 01D: I/O Layer

**Phase**: 1D — Foundation (I/O Layer)
**Last edited**: 2026-02-25

---

## Before Proceeding

Review the following documents before making any edits to plans or writing any code:

- [`docs/planning/active/refactors/full_codebase_refactor/full_codebase_refactor.md`](../full_codebase_refactor.md) — master refactor plan; update it if any decisions made here affect the overall plan.
- [`.prompts/philosphy.md`](../../../../../.prompts/philosphy.md) — project development philosophy; all implementation decisions must align with it.

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

- **No defaults on arguments** (per philosophy.md) — except where a `None` means "compute automatically" (e.g., `encoding=None` means `default_zarr_encoding` is called internally).
- All functions raise `ss_fha.exceptions.DataError` on failure, not raw I/O exceptions — wrap file operations in try/except and re-raise with context (operation, filepath, reason).
- `overwrite=False` in `write_zarr` raises `DataError` if path exists — no silent overwrites.
- `crs_epsg` in `create_mask_from_shapefile` is a required argument, not a default.

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

Where TRITON-SWMM_toolkit has reusable I/O utilities, import them directly rather than duplicating. Document the import source with a comment.

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
| Zarr v2 vs v3 format differences | Pin zarr version in environment; use `zarr_format=2` explicitly in `write_zarr` |
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

- [ ] `src/ss_fha/io/zarr_io.py` implemented with all four functions
- [ ] `src/ss_fha/io/netcdf_io.py` implemented
- [ ] `src/ss_fha/io/gis_io.py` implemented
- [ ] All functions raise `DataError` (not raw I/O exceptions) on failure
- [ ] `crs_epsg` is a required argument in `create_mask_from_shapefile` (no default)
- [ ] All `tests/test_io.py` tests pass with synthetic data
- [ ] Refactoring status block updated in `_old_code_to_refactor/__utils.py`
- [ ] `full_codebase_refactor.md` tracking table updated
- [ ] **Move this document to `implemented/` once all boxes above are checked**
