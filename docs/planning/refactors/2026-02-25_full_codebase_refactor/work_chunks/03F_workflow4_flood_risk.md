# Work Chunk 03F: Workflow 4 — Flood Risk Assessment

**Phase**: 3F — Analysis Modules + Runner Scripts (Flood Risk)
**Last edited**: 2026-02-25

---

## Before Proceeding

Review the following documents before making any edits to plans or writing any code:

- [`docs/planning/refactors/2026-02-25_full_codebase_refactor/full_codebase_refactor.md`](../full_codebase_refactor.md) — master refactor plan; update it if any decisions made here affect the overall plan.
- [`CONTRIBUTING.md`](../../../../CONTRIBUTING.md) — project development philosophy; all implementation decisions must align with it.

**Prerequisite**: Workflow 1 outputs (03A). Optionally uses Workflow 2 CI outputs (03B).

---

## Task Understanding

### Requirements

Implement Workflow 4 (Flood Risk Assessment) — impact analysis of flooding on buildings, roads, parcels, and sidewalks by AOI.

**Replaces**: `f1_box_and_whiskers_event_rtrn_vs_fld_rtrn.py`, `f2_comparing_event_and_flood_prob_by_aoi.py`

**Files to create:**

1. `src/ss_fha/analysis/flood_risk.py`:
   - Load Workflow 1 flood probability zarrs
   - Load building, road, parcel, sidewalk shapefiles (via `ss_fha.io.gis_io`)
   - Compute impact return periods per feature type and AOI
   - Optionally incorporate Workflow 2 CI bounds if available
   - Write impact output zarrs/CSVs

2. `src/ss_fha/runners/flood_risk_runner.py`:
   - CLI args: `--config <yaml>`
   - Only runs when `toggle_flood_risk=True` (validate in runner)
   - Logs completion marker

### Key Design Decisions

- **AOI shapefile is required** when `toggle_flood_risk=True` — validate in preflight.
- Flood risk analysis is the last workflow and has no downstream dependents in the current design.
- Depth thresholds for impact assessment come from `config.depth_thresholds_m` — no defaults in function args.
- Keep the `f1` (event return vs. flood return comparison) and `f2` (AOI comparison) logic distinct within `flood_risk.py` — don't conflate them.

### Success Criteria

- Runner executes end-to-end with synthetic building/road shapefiles and flood probability zarr
- Output contains expected impact metrics per feature type and AOI
- Toggle guard prevents execution when disabled

---

## Evidence from Codebase

Before implementing, inspect:

1. `_old_code_to_refactor/f1_box_and_whiskers_event_rtrn_vs_fld_rtrn.py`
2. `_old_code_to_refactor/f2_comparing_event_and_flood_prob_by_aoi.py`
3. `src/ss_fha/core/geospatial.py` (02D) — `compute_flood_impact_return_periods()`
4. `src/ss_fha/io/gis_io.py` (01D) — shapefile reading

---

## File-by-File Change Plan

### New Files

| File | Purpose |
|------|---------|
| `src/ss_fha/analysis/flood_risk.py` | Workflow 4 orchestration |
| `src/ss_fha/runners/flood_risk_runner.py` | CLI runner |
| (add tests to) `tests/test_end_to_end.py` | Workflow 4 integration test |

### Modified Files

| File | Change |
|------|--------|
| `_old_code_to_refactor/f1_*.py`, `f2_*.py` | Add refactoring status blocks |

---

## Risks and Edge Cases

| Risk | Mitigation |
|------|-----------|
| Missing shapefiles when toggle is on | `preflight_validate` in Phase 1E catches this before runner starts |
| CRS mismatch between flood grid and shapefiles | Re-project in `gis_io` layer; assert CRS consistency before spatial operations |
| `f1` and `f2` logic may share significant code | Extract shared helpers into `flood_risk.py` module-level functions |

---

## Validation Plan

```bash
python -m ss_fha.runners.flood_risk_runner --config /tmp/ssfha_test/config.yaml
pytest tests/test_end_to_end.py::test_workflow4_flood_risk -v
```

---

## Documentation and Tracker Updates

- Update `full_codebase_refactor.md` tracking table: `f1_*`, `f2_*` → `COMPLETE`.

---

## Definition of Done

- [ ] `src/ss_fha/analysis/flood_risk.py` implemented
- [ ] `src/ss_fha/runners/flood_risk_runner.py` implemented with toggle guard
- [ ] Depth thresholds sourced from config (no hardcoded values)
- [ ] Integration test with synthetic building/road shapefiles passes
- [ ] `full_codebase_refactor.md` tracking table updated
- [ ] **Move this document to `../implemented/` once all boxes above are checked**
