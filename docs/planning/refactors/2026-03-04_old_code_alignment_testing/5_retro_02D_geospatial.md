---
created: 2026-03-04
last_edited: 2026-03-04 — initial draft
---

# Phase 5: Retroactive — 02D Geospatial

## Dependencies

**Upstream**: Phase 1.
**Downstream**: None.

## Task Understanding

Add old-code alignment tests for geospatial computation functions in `core.geospatial`. The old equivalents are in `__utils.py`.

Functions to align:
- `return_ds_gridsize(ds)` → `core.geospatial.grid_cell_size_m(da)` — simple; verify same result on synthetic grid
- `return_impacted_features(da_features_impacted, sorted_unique_features_in_aoi, event_number_chunksize)` → `core.geospatial.return_impacted_features(...)` — uses `xr.apply_ufunc`; verify boolean mask output matches
- `return_number_of_impacted_features(da_unique_features_impacted, feature_type)` → `core.geospatial.return_number_of_impacted_features(...)` — count of impacted features per event
- `compute_min_rtrn_pd_of_impact_for_unique_features(s_grp, n_years)` → `core.geospatial.compute_min_return_period_of_feature_impact(...)` — minimum return period per feature

I/O functions (`create_mask_from_shapefile`, `create_flood_metric_mask`) are excluded from alignment scope (they are I/O wrappers over geopandas/rasterio — equivalence is guaranteed by the library, not our logic).

## File-by-File Change Plan

### New Files

| File | Purpose |
|------|---------|
| `tests/test_old_code_alignment/test_align_geospatial.py` | Alignment tests for 02D |

## Implementation Notes

For `return_impacted_features` and `return_number_of_impacted_features`, construct a synthetic `da_features_impacted` DataArray with known integer feature IDs per cell per event. The old function uses `xr.apply_ufunc` with `retrieve_unique_feature_indices` as the inner function. The new version should produce identical boolean masks.

For `compute_min_rtrn_pd_of_impact_for_unique_features`, the old function takes a `pd.Series` grouped by feature ID. Construct synthetic grouped data and verify minimum return period computation.

## Validation Plan

```bash
conda run -n ss-fha pytest tests/test_old_code_alignment/test_align_geospatial.py -v
conda run -n ss-fha pytest tests/ -v
```

## Definition of Done

- [ ] `test_align_geospatial.py` written
- [ ] `return_ds_gridsize` vs. `grid_cell_size_m` equivalence test
- [ ] `return_impacted_features` vs. new equivalent alignment test
- [ ] `return_number_of_impacted_features` vs. new equivalent alignment test
- [ ] `compute_min_rtrn_pd_of_impact_for_unique_features` vs. new equivalent alignment test
- [ ] All tests pass
- [ ] Move this doc to `implemented/`

## Lessons Learned

_(fill in after implementation)_
