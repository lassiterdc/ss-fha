# Work Chunk 02D: Core Geospatial Module

**Phase**: 2D — Core Computation (Geospatial)
**Last edited**: 2026-02-25

---

## Before Proceeding

Review the following documents before making any edits to plans or writing any code:

- [`docs/planning/active/refactors/full_codebase_refactor/full_codebase_refactor.md`](../full_codebase_refactor.md) — master refactor plan; update it if any decisions made here affect the overall plan.
- [`.prompts/philosphy.md`](../../../../../.prompts/philosphy.md) — project development philosophy; all implementation decisions must align with it.

**Prerequisite**: Work chunks 01D (I/O layer) and 02A complete.

---

## Task Understanding

### Requirements

Extract and port the geospatial computation functions from `_old_code_to_refactor/__utils.py` into `src/ss_fha/core/geospatial.py`. The I/O operations (shapefile reading, zarr reading) remain in `ss_fha.io`; this module handles the spatial computation on already-loaded data objects.

**Functions to migrate (verify exact names in `__utils.py`):**

- `create_mask_from_shapefile()` — NOTE: This overlaps with `ss_fha.io.gis_io.create_mask_from_shapefile` from 01D. Resolve the boundary: I/O module handles file loading and returns a mask DataArray; core/geospatial.py handles masking operations on already-loaded arrays.
- `return_mask_dataset_from_polygon()` — spatial masking from polygon geometry
- `return_impacted_features()` — identifies features (roads, buildings) within flood depth threshold
- `create_flood_metric_mask()` — creates boolean mask for flood metric exceedance
- `compute_floodarea_retrn_pds()` — computes flood area return periods
- `compute_flood_impact_return_periods()` — computes impact return periods by feature type

### Key Design Decisions

- **Resolve the I/O boundary**: `gis_io.create_mask_from_shapefile()` (from 01D) handles reading a shapefile and producing a mask. `core/geospatial.py` should handle masking operations that operate on already-loaded `xr.DataArray`, `gpd.GeoDataFrame` objects. If the old code conflates these, split them cleanly.
- **CRS is an explicit argument** wherever spatial operations depend on it — no default EPSG.
- **No I/O in any function**.

### Success Criteria

- All geospatial functions operate on in-memory data objects
- Tests use synthetic geometries with known overlap areas and verify correct masking
- No circular imports between `ss_fha.io.gis_io` and `ss_fha.core.geospatial`

---

## Evidence from Codebase

Before implementing, inspect:

1. `_old_code_to_refactor/__utils.py` — geospatial functions
2. `_old_code_to_refactor/f1_box_and_whiskers_event_rtrn_vs_fld_rtrn.py` — how impact functions are called
3. `src/ss_fha/io/gis_io.py` (01D) — determine the I/O boundary before porting

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
| `_old_code_to_refactor/__utils.py` | Update refactoring status block |

---

## Risks and Edge Cases

| Risk | Mitigation |
|------|-----------|
| Boundary between I/O and computation is blurry in old code | Audit carefully; document the boundary decision in a module docstring |
| CRS mismatch between shapefile and raster grid | Geospatial functions should assert or require matched CRS; re-projection in I/O layer |
| Flood impact functions have complex nested logic | Port faithfully first; test against known-good small examples |

---

## Validation Plan

```bash
pytest tests/test_geospatial.py -v
pytest tests/test_geospatial.py::test_mask_known_geometry -v
pytest tests/test_geospatial.py::test_impact_features_known_overlap -v
```

---

## Documentation and Tracker Updates

- Update `full_codebase_refactor.md` tracking table: `__utils.py` — geospatial functions migrated.

---

## Definition of Done

- [ ] `src/ss_fha/core/geospatial.py` implemented; all functions operate on in-memory data
- [ ] I/O boundary clearly documented (module docstring)
- [ ] CRS always an explicit argument
- [ ] No I/O in any function
- [ ] Tests with synthetic geometries pass
- [ ] Refactoring status block updated in `_old_code_to_refactor/__utils.py`
- [ ] `full_codebase_refactor.md` tracking table updated; `__utils.py` moved to `COMPLETE` if fully migrated
- [ ] **Move this document to `implemented/` once all boxes above are checked**
