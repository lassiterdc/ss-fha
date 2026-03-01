# Work Chunk 02D: Core Geospatial Module

**Phase**: 2D — Core Computation (Geospatial) + I/O Layer updates
**Last edited**: 2026-02-26

---

## Before Proceeding

Review the following documents before making any edits to plans or writing any code:

- [`docs/planning/refactors/2026-02-25_full_codebase_refactor/full_codebase_refactor.md`](../full_codebase_refactor.md) — master refactor plan; update it if any decisions made here affect the overall plan.
- [`CONTRIBUTING.md`](../../../../CONTRIBUTING.md) — project development philosophy; all implementation decisions must align with it.

**Prerequisite**: Work chunks 01D (I/O layer) and 02A complete.

---

## Task Understanding

### Part A: `io/gis_io.py` updates

The existing `gis_io.py` (implemented in 01D) uses filetype-specific function names and reads files directly in some places that should be a canonical loader. Per philosophy.md, filetype strings must not appear in non-I/O function names.

**Changes to `gis_io.py`:**

1. **`read_shapefile()` → `load_geospatial_data_from_file(path, clip_to)`**
   - Canonical loader for any OGR-readable vector format
   - Validates that `path` has a recognized extension: `.shp`, `.geojson`, `.json`, `.gpkg`
   - Raises `DataError` for unsupported extensions
   - Clipping behavior unchanged (`clip_to: gpd.GeoDataFrame | None`)

2. **`create_mask_from_shapefile()` → `create_mask_from_polygon()`**
   - Accepts any of: a `Path`/`str` file path, a `gpd.GeoDataFrame`, a `gpd.GeoSeries`, or a Shapely `Polygon`/`MultiPolygon` geometry
   - If a file path is passed, calls `load_geospatial_data_from_file()` internally (no clip — masking always uses the full geometry)
   - `crs_epsg: int` remains a required argument — no default CRS
   - Returns a boolean `xr.DataArray` (same behavior as before)
   - No filetype string in name — `create_mask_from_polygon` is the correct name regardless of input type

3. **`rasterize_features()`** — unchanged; already takes in-memory GeoDataFrame

**Validation layer update**: Any `SsfhaConfig` geospatial file path field must validate that the extension is one of `.shp`, `.geojson`, `.json`, `.gpkg`. Update `src/ss_fha/validation.py` accordingly.

**Rule enforced**: Function names must not contain filetype strings (`shapefile`, `geojson`, etc.) unless the function is exclusively a file-reading or file-writing operation.

---

### Part B: New `core/geospatial.py`

Pure spatial computation on in-memory data objects. No file I/O in any function.

**Functions to port from `__utils.py`** (verify exact names and signatures):

| Old function | Notes |
|---|---|
| `retrieve_unique_feature_indices()` (line ~2814) | Helper for `return_impacted_features()` |
| `return_impacted_features()` (line ~2821) | Identifies features within flood depth threshold |
| `compute_number_of_unique_indices()` (line ~2847) | Helper |
| `return_number_of_impacted_features()` (line ~2851) | Helper |
| `compute_min_rtrn_pd_of_impact_for_unique_features()` (line ~2869) | Per-feature minimum return period |
| `return_ds_gridsize()` (line ~464) | 2-line grid cell size utility |

**Already migrated in Phase 1D — do not re-port:**
- `create_mask_from_shapefile()` → renamed `create_mask_from_polygon()` in Part A above
- `create_flood_metric_mask()` → `gis_io.rasterize_features()`

**`return_mask_dataset_from_polygon()`**: The old function wraps `create_mask_from_shapefile()` to convert a numpy mask to an `xr.DataArray`. With the new `create_mask_from_polygon()` already returning an `xr.DataArray`, this wrapper is likely redundant. Inspect during implementation — if no callers need a separate `return_mask_dataset_from_polygon`, do not port it.

**Deferred to Phase 3F** (orchestration, not pure computation):
- `compute_flood_impact_return_periods()`
- `compute_floodarea_retrn_pds()`
- `compute_volume_at_max_flooding()`
- `compute_flooded_area_by_depth_threshold()`

---

### Key Design Decisions

- **No I/O in any `core/geospatial.py` function**
- **CRS is an explicit argument** wherever spatial operations depend on it — no default EPSG
- **`is_ss` not `ensemble`**: If any ported function has an `ensemble: bool` parameter distinguishing SSFHA from BDS, rename to `is_ss: bool` per philosophy.md terminology
- **No default arguments** unless the default is almost always the correct choice (per philosophy.md)
- **Fail-fast**: Non-square grid cells in any area computation must raise an exception, not print a warning
- **Unused legacy parameters** (e.g., `ASSIGN_DUP_VALS_MAX_RETURN` appearing in signatures but never used in the body): drop them — do not port vestigial arguments
- **No circular imports** between `ss_fha.io.gis_io` and `ss_fha.core.geospatial`

---

### Success Criteria

- All geospatial functions in `core/geospatial.py` operate on in-memory data objects
- `create_mask_from_polygon()` in `gis_io.py` accepts file paths, GeoDataFrames, and geometry objects
- `load_geospatial_data_from_file()` is the canonical loader; `read_shapefile()` removed
- No filetype-specific strings in non-I/O function names
- Tests use synthetic geometries with known overlap areas and verify correct masking
- No circular imports between `ss_fha.io.gis_io` and `ss_fha.core.geospatial`
- Validation layer enforces recognized geospatial file extensions

---

## Evidence from Codebase

Before implementing, inspect:

1. `_old_code_to_refactor/__utils.py` — geospatial functions (lines ~464–498, ~969–1041, ~2814–2975)
2. `_old_code_to_refactor/f1_box_and_whiskers_event_rtrn_vs_fld_rtrn.py` — how impact functions are called (context for Phase 3F)
3. `src/ss_fha/io/gis_io.py` (01D) — existing implementation to be updated
4. `src/ss_fha/validation.py` — file extension validation to be added
5. `src/ss_fha/core/flood_probability.py` and `event_statistics.py` — style and pattern reference

---

## File-by-File Change Plan

### New Files

| File | Purpose |
|------|---------|
| `src/ss_fha/core/geospatial.py` | Geospatial computation functions |
| `tests/test_geospatial.py` | Tests with synthetic geometries |

### Modified Files

| File | Change |
|------|--------|
| `src/ss_fha/io/gis_io.py` | Rename `read_shapefile` → `load_geospatial_data_from_file`; rename `create_mask_from_shapefile` → `create_mask_from_polygon` with broadened input types |
| `src/ss_fha/validation.py` | Add geospatial file extension validation |
| `tests/test_io.py` | Update tests for renamed/changed functions (GIS section) |
| `_old_code_to_refactor/__utils.py` | Update refactoring status block |

---

## Risks and Edge Cases

| Risk | Mitigation |
|------|------------|
| `create_mask_from_polygon` must handle 4 input types cleanly | Use `isinstance` dispatch; raise `DataError` with clear message for unsupported types |
| CRS mismatch between geometry and raster grid | Functions must assert or require matched CRS; re-projection is the caller's responsibility (or explicit in the function if it accepts a file path) |
| Vestigial parameters in old functions | Drop any parameter that appears in the signature but is never referenced in the body |
| Non-square grid cells | Raise exception in `return_ds_gridsize()` if x and y cell sizes differ (replaces the old `print("warning: ...")`) |
| `return_mask_dataset_from_polygon` may be redundant | Inspect callers before porting; skip if the new `create_mask_from_polygon` already returns `xr.DataArray` |

---

## Validation Plan

```bash
pytest tests/test_geospatial.py -v
pytest tests/test_io.py -v
pytest tests/test_geospatial.py::test_mask_known_geometry -v
pytest tests/test_geospatial.py::test_impact_features_known_overlap -v
pytest tests/test_io.py::test_create_mask_from_polygon_filepath -v
pytest tests/test_io.py::test_create_mask_from_polygon_geodataframe -v
```

---

## Documentation and Tracker Updates

- Update `full_codebase_refactor.md` tracking table: `__utils.py` — geospatial primitives migrated; orchestration functions (floodarea/impact return periods) noted as deferred to Phase 3F.
- Update `gis_io.py` module docstring to reflect new function names and the canonical loader pattern.

---

## Definition of Done

- [x] `src/ss_fha/io/gis_io.py` updated: `load_geospatial_data_from_file` replaces `read_shapefile`; `create_mask_from_polygon` replaces `create_mask_from_shapefile` with broadened inputs
- [x] `src/ss_fha/validation.py` updated with geospatial file extension validation
- [x] `src/ss_fha/core/geospatial.py` implemented; all functions operate on in-memory data
- [x] I/O boundary clearly documented (module docstring in `geospatial.py`)
- [x] CRS always an explicit argument; no default EPSG
- [x] No I/O in any `core/geospatial.py` function
- [x] No filetype-specific strings in non-I/O function names
- [x] Tests with synthetic geometries pass (`test_geospatial.py`, `test_io.py` GIS section) — 165/165
- [x] Refactoring status block updated in `_old_code_to_refactor/__utils.py`
- [x] `full_codebase_refactor.md` tracking table updated
- [x] **Move this document to `../implemented/` once all boxes above are checked**

---

## Decision Log

| Decision | Resolution |
|----------|-----------|
| `compute_floodarea_retrn_pds` and `compute_flood_impact_return_periods` scope | Deferred to Phase 3F — orchestration functions, not pure computation |
| `create_mask_from_shapefile` naming and input types | Renamed `create_mask_from_polygon`; accepts file path, GeoDataFrame, GeoSeries, or Shapely geometry |
| `read_shapefile` generalization | Renamed `load_geospatial_data_from_file`; validates extension; canonical loader |
| Helper functions (`retrieve_unique_feature_indices`, etc.) | Included in `core/geospatial.py` — required by the ported spatial primitives |
| `return_ds_gridsize` | Include in `core/geospatial.py`; non-square grid → raise exception |
| `compute_volume_at_max_flooding`, `compute_flooded_area_by_depth_threshold` | Deferred to Phase 3F — use domain constants, belong in analysis layer |
| `ensemble` parameter naming | Rename to `is_ss` on any porting per philosophy.md |
| `ASSIGN_DUP_VALS_MAX_RETURN` vestigial parameter | Drop — not ported |
