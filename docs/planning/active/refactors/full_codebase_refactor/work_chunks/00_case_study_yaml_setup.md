# Work Chunk 00: Case Study YAML Setup

**Phase**: 0 — Pre-Implementation (Config and Data Inventory)
**Last edited**: 2026-02-25

---

## Before Proceeding

Review the following documents before making any edits to plans or writing any code:

- [`docs/planning/active/refactors/full_codebase_refactor/full_codebase_refactor.md`](../full_codebase_refactor.md) — master refactor plan; update it if any decisions made here affect the overall plan.
- [`.prompts/philosphy.md`](../../../../../.prompts/philosphy.md) — project development philosophy; all implementation decisions must align with it.

**Prerequisite**: None — this is the first task and has no code dependencies.

---

## Purpose

Creating the case study YAML files early is a forcing function. It requires making concrete decisions about:

- Which parameters are case-study-specific vs. analysis-method defaults
- Which input files exist, what they are named, and where they live
- Which files are missing and must be tracked down or derived
- How the multi-FHA analysis config structure works in practice before any code commits to it

**No code is written in this chunk.** The deliverables are YAML files and documentation only. Any `TODO` entry in a YAML is an explicit gap that must be resolved before Phase 6 (case study validation). Better to surface them now.

---

## Staged Data Inventory

The local staging directory is `/mnt/d/Dropbox/_GradSchool/repos/ss-fha/hydroshare_data`.
All paths below are relative to that root. Inspected 2026-02-25.

### `model_results/` — TRITON peak flood depth outputs (Zarr)

All SS zarrs share the same structure: dims `(x: 526, y: 513, event_iloc: 3798)`, single data variable `max_wlevel_m`, coordinates include `x`, `y`, `event_iloc`, and a scalar `ensemble_type`.

| File | Description | Dims / Key Coords | Status |
|------|-------------|-------------------|--------|
| `ss_tritonswmm.zarr` | SS compound simulation peak flood depths (TRITON+SWMM coupled) | `event_iloc=3798`, `ensemble_type='compound'` | ✓ Present |
| `ss_tritonswmm_rainonly.zarr` | SS rain-only simulation peak flood depths | `event_iloc=3798`, `ensemble_type` value TBC | ✓ Present |
| `ss_tritonswmm_surgeonly.zarr` | SS surge-only simulation peak flood depths | `event_iloc=3798`, `ensemble_type` value TBC | ✓ Present |
| `ss_triton_only.zarr` | SS TRITON-only (no SWMM coupling) peak flood depths | `event_iloc=3798` | ✓ Present |
| `design_storm_tritonswmm.zarr` | Design storm compound peak flood depths | `return_pd_yrs=[1,2,10,100]`, `rain_duration_h=24`, `event_type='compound'`, `simtype='compound'`, `model='tritonswmm'` | ✓ Present |
| `design_storm_tritonswmm_rainonly.zarr` | Design storm rain-only peak flood depths | Same coords as above, rain-only variant | ✓ Present |
| `design_storm_tritonswmm_surgeonly.zarr` | Design storm surge-only peak flood depths | Same coords as above, surge-only variant | ✓ Present |
| `obs_tritonswmm.zarr` | Observed event peak flood depths — needed for PPCCT (Workflow 3) | Dims TBC — verify match SS zarrs | ✓ Present |

**Note on design storm zarr structure**: The design storm zarrs are indexed by `return_pd_yrs` (not `event_iloc`), reflecting that each design storm *is* a return-period event, not a member of the stochastic ensemble. The `(x: 526, y: 513)` grid is the same as the SS zarrs. Rain duration is fixed at 24 hr for the combined storm.

### `events/` — Event summaries and time series

| File | Description | Shape / Dims | Status |
|------|-------------|-------------|--------|
| `ss_simulation_summaries.csv` | Per-event meteorological summaries for all 3,798 SS simulations. Includes event type (compound/rain/surge), rescaling parameters, observed event linkages, and ~40 rainfall/surge intensity statistics. | `(3798, 40)` | ✓ Present |
| `ss_event_iloc_mapping.csv` | Maps flat `event_number` (0–3797) to `(year, event_type, event_id)` — the 3D index used in time series NetCDFs. Essential for linking zarr `event_iloc` to event metadata. | `(3798, 4)` cols: `event_number, year, event_type, event_id` | ✓ Present |
| `ss_simulation_time_series.nc` | Per-event time series for all SS simulations: rainfall intensity, water level, surge, tide, plus 6 rain gage IDs (156, 171, 170, 155, 140, 141). `year` dim spans 954 values (not all 1000 — some years had no events). `event_id` max=5 (up to 5 events per year per type). | `(event_type=3, year=954, event_id=5, timestep=3261)` ~4 GB | ✓ Present |
| `obs_event_summaries_from_yrs_with_complete_coverage.csv` | Per-event meteorological summaries for 71 observed events from years with complete data coverage. Same intensity stat schema as SS summaries but richer (includes observed data source flags). | `(71, 61)` | ✓ Present |
| `obs_event_iloc_mapping.csv` | Maps flat `event_iloc` to `(year, event_type, event_id)` for the 71 observed events. | `(71, 4)` cols: `event_iloc, year, event_type, event_id` | ✓ Present |
| `obs_event_tseries_from_yrs_with_complete_coverage.nc` | Per-event time series for observed events. Same variables as SS time series plus `first_obs_tstep_w_rainfall`. `year` spans 18 (years with complete coverage). | `(year=18, event_type=3, event_id=5, timestep=2174)` ~47 MB | ✓ Present |
| `design_storm_combined.nc` | Design storm time series for compound (combined) storms. `year` dim = 4, representing the 4 return periods [1, 2, 10, 100 yr]. Same variables as SS time series. | `(year=4, timestep=336)` | ✓ Present |
| `design_storm_rainonly.nc` | Design storm time series, rain-only variant | `(year=4, timestep=336)` | ✓ Present |
| `design_storm_surgeonly.nc` | Design storm time series, surge-only variant | `(year=4, timestep=336)` | ✓ Present |
| tide gage data | Not a staged input file. The NOAA tide gage CSV (`f_noaa_tide_gage_csv`) is referenced only in `compute_mean_high_high_tide_from_NOAA_tide_gage()` in `__utils.py`, which is called from plotting functions only — not from any computation pipeline. Not needed as a data input. | N/A | Not required |
| empirical return period CSVs | Not staged input files. `F_RTRN_PDS_RAINFALL` and `F_RTRN_PDS_SEA_WATER_LEVEL` are **outputs** of the event statistics runner (`d0_computing_event_statistic_probabilities.py`), cached and reloaded if they already exist. They are intermediate outputs, not external inputs. They will be written to `output_dir/event_statistics/` by the refactored pipeline. | N/A | Not required as inputs |

**Note on time series variable names**: The integer variables `156`, `171`, `170`, `155`, `140`, `141` in both SS and observed NetCDFs appear to be rain gage station IDs (or SWMM subcatchment IDs). Their meaning must be confirmed before the I/O layer can label them correctly. This is a **decision point for 01D (I/O layer)**.

### `geospatial/` — Shapefiles and rasters

| File | Description | CRS | Clip Status | Status |
|------|-------------|-----|------------|--------|
| `norfolk_wshed_epsg32147_state_plane_m.shp` | Norfolk watershed boundary, single polygon. CRS confirmed EPSG:32147. Bounds ~3696718–3698614 E, ~1059893–1061741 N (state plane meters). | EPSG:32147 | N/A | ✓ Present |
| `fema/100yr_depths_m.tif` | FEMA 100-yr flood depth raster in meters. Used for design comparison (Workflow 5). | Unknown — verify | N/A | ✓ Present |
| `Street_Centerline_-_City_of_Norfolk.shp` | City of Norfolk road centerlines — **raw, city-wide, not clipped to watershed**. | Unknown — verify | ✗ Unclipped | ✓ Present (raw) |
| `Sidewalk_-_City_of_Norfolk.shp` | City of Norfolk sidewalks — **raw, city-wide, not clipped to watershed**. | Unknown — verify | ✗ Unclipped | ✓ Present (raw) |
| `buildings_from_ms_github/va_buildings.shp` | Virginia statewide building footprints from Microsoft ML dataset — **raw, statewide, not clipped**. | Unknown — verify | ✗ Unclipped | ✓ Present (raw) |
| `Parcel_Boundaries/Parcel_Boundaries.shp` | Norfolk parcel boundaries. Clipping status unknown. | Unknown — verify | ? Unknown | ✓ Present |
| `aoi.shp` | Not used. Workflow 4 spatial subsetting will use the watershed shapefile directly. `F_MITIGATION_AOIS` in old code was used only in `e2_investigating_flood_depth_area_probability.py`; `SUBAREAS_FOR_COMPUTING_IMPACT_RETURN_PDS = ["watershed"]` confirms the watershed was the only subarea in practice. No AOI shapefile needed. | N/A | N/A | Not required |

**Critical decision — raw vs. pre-clipped geospatial files**: The old code used pre-clipped versions of roads, buildings, and sidewalks. The staged files are raw. Two options:
1. **Clip on load** in `gis_io.py` (library handles it; accepts raw files from HydroShare)
2. **Pre-clip and re-stage** (simpler I/O layer; clipped files go to HydroShare)

This decision affects `01D` (I/O layer design). It must be made here and documented. See "Decisions to Make" section.

---

## Data Tracking Checklist

Items that must be resolved before Phase 6 (case study validation). Track status here as items are resolved.

### Missing Files — Must Track Down or Derive

- [x] **Observed TRITON output zarr** (`obs_tritonswmm.zarr`) — **RESOLVED**: staged 2026-02-25. Verify dim structure matches SS zarrs before implementing PPCCT (Workflow 3).

*No other files are missing.* Tide gage data, empirical return period CSVs, and the AOI shapefile are not required inputs — see inventory table notes above.

### Values Requiring Confirmation

- [ ] **`n_years_synthesized: 1000`** — Record in `norfolk_ssfha_compound.yaml` (and all FHA variant YAMLs). This is the total number of synthetic years in the SS weather model run, including years with no events. The SS time series contains only 954 years (those with ≥1 event); 1000 is confirmed by `N_YEARS_SYNTHESIZED = 1000` in `__inputs.py`. This value is the denominator for all simulated return period calculations — it must be explicitly set in config and never inferred from data dimensions. See notes in 01B and 02B.

- [ ] **`n_years_observed: 18`** — Record in `norfolk_ssfha_compound.yaml`. This is the total length of the observed record. For Norfolk, all 18 observed years have ≥1 event (confirmed: `obs_ds.year` has 18 values), so `len(obs_ds.year) == n_years_observed` happens to be true here. However other case studies may have event-free observed years, so this must always be set explicitly — never inferred from data dimensions. Used as the denominator for observed return period calculations in PPCCT. See notes in 01B and 02B.

### Files Present but Requiring Verification or Decisions

- [ ] **Confirm CRS of all geospatial files** (roads, sidewalks, buildings, parcels, FEMA raster)
  - Watershed is confirmed EPSG:32147. All others need verification.
  - Action: Run `geopandas.read_file(...).crs` / `rasterio.open(...).crs` for each.

- [ ] **Decide: raw vs. pre-clipped geospatial files** (roads, sidewalks, buildings, parcels)
  - See "Decisions to Make" section below.
  - Action: Make decision; document in README and YAML comments; update `01D` planning doc if it affects I/O layer design.

- [ ] **Confirm meaning of integer variable names** (156, 171, 170, 155, 140, 141) in time series NetCDFs
  - Appear in both SS and observed time series. Likely NOAA rain gage station IDs or SWMM node IDs.
  - Action: Check TRITON-SWMM_toolkit outputs or documentation for variable naming convention.

- [ ] **Confirm `N_YEARS_SYNTHESIZED`**
  - `__inputs.py` has `N_YEARS_SYNTHESIZED = 1000` but the SS time series has `year` dim = 954 (not 1000 — some years had no simulated events). The TRITON zarr has `event_iloc = 3798`. The actual count must be derived from the data, not from a hardcoded constant.
  - Action: Confirm `N_YEARS_SYNTHESIZED` is truly 1000 (and 954 is just years with ≥1 event), and that this distinction is handled correctly when computing empirical return periods.

- [ ] **Confirm design storm `rain_duration_h`**
  - Staged design storm zarrs have `rain_duration_h = 24`. The `__inputs.py` `TARGET_DESIGN_STORM_DURATION_HRS_FOR_COMPARISON = 24` corroborates this. But `LST_DESIGN_STORM_DURATIONS_TO_SIMULATE = [6, 12, 24]` suggests 6-hr and 12-hr variants may also exist or were planned.
  - Action: Confirm that only the 24-hr design storm is in scope for the comparison, or locate/generate the 6-hr and 12-hr variants.

- [ ] **Confirm `RETURN_PERIODS` scope**
  - `__inputs.py` has `RETURN_PERIODS = [1, 2, 10, 100]` with the comment "this can't be changed because this is all that is available for the tide gage return periods." The design storm zarrs confirm `return_pd_yrs = [1, 2, 10, 100]`. This should be a default in `config/defaults.py` but users must understand it is constrained by upstream data.
  - Action: Confirm and document in `norfolk_study_area.yaml` with a clear comment about the constraint.

- [ ] **Locate or confirm absence of `ppct_alpha` / `FLD_RTRN_PD_ALPHA` as Norfolk-specific**
  - `ppct_alpha = 0.05` (PPCCT significance threshold) and `FLD_RTRN_PD_ALPHA = 0.1` (90% CI, matching NOAA Atlas 14) are in `__inputs.py`. Determine whether these are generic analysis defaults (→ `config/defaults.py`) or Norfolk-specific choices (→ `norfolk_study_area.yaml`).

---

## Decisions to Make and Document

Work through each explicitly. Record decision and rationale in the YAML as comments or in `README.md`.

### Decision 1: Raw vs. pre-clipped geospatial files

**Context**: Roads, sidewalks, and buildings in staging are raw city-wide/statewide files. Old code used pre-clipped files.

**Option A — Clip on load** (`gis_io.py` clips to watershed bbox/polygon on read):
- HydroShare holds raw files; any case study can use them
- I/O layer is more complex; clipping adds latency and may need tuning per file type
- More general; raw files are easier to source

**Option B — Pre-clip before staging** (clipped files go to HydroShare):
- I/O layer stays simple (just read and mask)
- Pre-clipped files are case-study-specific; a different study area requires re-clipping
- Clipping scripts must be tracked and reproducible

**Recommendation**: Option A (clip on load), with the watershed shapefile as the clip boundary. This matches the library's design goal of being general-purpose. Document this as an `01D` requirement.

### Decision 2: `fha_id` naming convention

Propose canonical `fha_id` strings (used as Snakemake wildcards and output directory names):

| Config file | Proposed `fha_id` | `fha_approach` |
|-------------|-------------------|----------------|
| `norfolk_ssfha_compound.yaml` | `ssfha_compound` | `ssfha` |
| `norfolk_ssfha_rainonly.yaml` | `ssfha_rainonly` | `ssfha` |
| `norfolk_ssfha_surgeonly.yaml` | `ssfha_surgeonly` | `ssfha` |
| `norfolk_triton_only.yaml` | `ssfha_tritononly` | `ssfha` |
| `norfolk_design_storm_bds.yaml` | `bds_compound_24hr` | `bds` |

Record the chosen `fha_id` values in each YAML and in the README.

### Decision 3: MCDS scope

**Context**: Old code includes MCDS (Monte Carlo design storm) analyses with multivariate AND/OR/univariate formulations. These have associated zarr outputs (`design_storm_tritonswmm_rainonly.zarr`, etc.) but no `fha_approach: mcds` YAML has been created.

**Question**: Is MCDS in scope for the initial refactor?

**Recommendation**: Defer MCDS configs to a later chunk (note it in the README as planned but out of scope for Phase 0). The design storm zarrs are already staged; the MCDS config YAMLs can be added in Phase 3E (design comparison work chunk).

### Decision 4: `constant_head_bndry_cndtn` value

The master plan's input file table lists "Constant head boundary condition value (scalar in config)" as a required input from TRITON-SWMM_toolkit. This value is not in `__inputs.py`. Determine:
- What is this parameter?
- Is it present in TRITON-SWMM_toolkit config files for the Norfolk run?
- Is it a fixed physical constant or a calibrated site-specific value?

If site-specific → `norfolk_study_area.yaml`. If a TRITON-SWMM_toolkit output parameter → document where to find it.

### Decision 5: `ppct_alpha` and `FLD_RTRN_PD_ALPHA` classification

- `ppct_alpha = 0.05`: Standard significance level for hypothesis testing. **Generic default** → `config/defaults.py`.
- `FLD_RTRN_PD_ALPHA = 0.1`: 90% CI chosen to match NOAA Atlas 14. This is a methodological choice, not Norfolk-specific. **Generic default** → `config/defaults.py`. Document the NOAA Atlas 14 rationale in a comment.

---

## Task Understanding

### Requirements

1. **`cases/norfolk_ssfha_comparison/norfolk_study_area.yaml`** — Norfolk-specific scalar parameters not in HydroShare and not in generic code defaults:
   - `crs_epsg: 32147` (confirmed from watershed shapefile)
   - Any other site-specific scalars identified during `__inputs.py` audit

2. **`cases/norfolk_ssfha_comparison/norfolk_ssfha_compound.yaml`** — Primary SS-FHA config (compound). All paths point to the local staging directory. Use `# TODO: missing — [description]` for absent files.

3. **`cases/norfolk_ssfha_comparison/norfolk_ssfha_rainonly.yaml`** — Rain-only SS-FHA config. Standalone YAML (no YAML anchors or inheritance).

4. **`cases/norfolk_ssfha_comparison/norfolk_ssfha_surgeonly.yaml`** — Surge-only SS-FHA config.

5. **`cases/norfolk_ssfha_comparison/norfolk_triton_only.yaml`** — TRITON-only config.

6. **`cases/norfolk_ssfha_comparison/norfolk_design_storm_bds.yaml`** — Basic design storm comparison config (`fha_approach: bds`).

7. **`cases/norfolk_ssfha_comparison/README.md`** — Directory purpose, YAML inventory, data gap tracking, decisions made.

### YAML Schema (Provisional)

These YAMLs are written to the *intended* `SSFHAConfig` schema (defined in 01B, not yet implemented). Field names are provisional; add a header comment noting they must be validated when 01B is implemented. 01B's Definition of Done should include loading these YAMLs as a smoke test.

```yaml
# PROVISIONAL — field names subject to change when SSFHAConfig (01B) is implemented.
# Validate all fields against SSFHAConfig when 01B is complete.

fha_id: ssfha_compound
fha_approach: ssfha        # "ssfha" | "bds" | "mcds"

project_name: norfolk_ssfha_comparison
project_dir: /path/to/project  # absolute; all relative paths resolve from here
output_dir: outputs/           # relative to project_dir

crs_epsg: 32147  # EPSG:32147 — Virginia State Plane South (meters); confirmed from watershed shapefile

n_years_synthesized: 1000  # total synthetic years in weather model run, INCLUDING years with no events.
                            # The SS time series contains only 954 years (those with ≥1 event).
                            # This is the denominator for ALL simulated return period calculations.
                            # DO NOT infer from len(ds.year) — that gives 954, not 1000.

n_years_observed: 18       # total years of observed record, INCLUDING any years with no events.
                            # For Norfolk all 18 observed years have ≥1 event, so len(obs_ds.year) == 18 here.
                            # Other case studies may have event-free observed years — always set explicitly.

triton_outputs:
  compound: /mnt/d/Dropbox/_GradSchool/repos/ss-fha/hydroshare_data/model_results/ss_tritonswmm.zarr

event_data:
  sim_event_summaries: /mnt/.../events/ss_simulation_summaries.csv
  sim_event_timeseries: /mnt/.../events/ss_simulation_time_series.nc
  sim_event_iloc_mapping: /mnt/.../events/ss_event_iloc_mapping.csv
  obs_event_summaries: /mnt/.../events/obs_event_summaries_from_yrs_with_complete_coverage.csv
  obs_event_timeseries: /mnt/.../events/obs_event_tseries_from_yrs_with_complete_coverage.nc
  obs_event_iloc_mapping: /mnt/.../events/obs_event_iloc_mapping.csv
  tide_gage_data: # TODO: missing — NOAA station 8638610 water level + surge CSV
  empirical_rainfall_return_periods: # TODO: missing — derive from SS ensemble in Phase 3C
  empirical_water_level_return_periods: # TODO: missing — derive from SS ensemble in Phase 3C

geospatial:
  watershed: /mnt/.../geospatial/norfolk_wshed_epsg32147_state_plane_m.shp
  roads: /mnt/.../geospatial/Street_Centerline_-_City_of_Norfolk.shp  # raw; clipped on load
  sidewalks: /mnt/.../geospatial/Sidewalk_-_City_of_Norfolk.shp       # raw; clipped on load
  buildings: /mnt/.../geospatial/buildings_from_ms_github/va_buildings.shp  # raw; clipped on load
  parcels: /mnt/.../geospatial/Parcel_Boundaries/Parcel_Boundaries.shp
  fema_100yr_depths: /mnt/.../geospatial/fema/100yr_depths_m.tif
  # No aoi.shp — spatial subsetting uses the watershed shapefile directly.

execution:
  mode: local_concurrent
  max_workers: 4

toggle_uncertainty: true
toggle_ppcct: true          # requires obs_tritonswmm.zarr — currently missing
toggle_flood_risk: true     # requires aoi.shp — currently missing
toggle_design_comparison: true

alt_fha_analyses:
  - cases/norfolk_ssfha_comparison/norfolk_ssfha_rainonly.yaml
  - cases/norfolk_ssfha_comparison/norfolk_ssfha_surgeonly.yaml
  - cases/norfolk_ssfha_comparison/norfolk_triton_only.yaml
  - cases/norfolk_ssfha_comparison/norfolk_design_storm_bds.yaml
```

---

## File-by-File Change Plan

### New Files

| File | Purpose |
|------|---------|
| `cases/norfolk_ssfha_comparison/README.md` | Directory purpose, YAML inventory, data gaps, decisions |
| `cases/norfolk_ssfha_comparison/norfolk_study_area.yaml` | Norfolk-specific scalar parameters (EPSG, etc.) |
| `cases/norfolk_ssfha_comparison/norfolk_ssfha_compound.yaml` | Primary SS-FHA config (compound) with local staging paths |
| `cases/norfolk_ssfha_comparison/norfolk_ssfha_rainonly.yaml` | Rain-only SS-FHA config |
| `cases/norfolk_ssfha_comparison/norfolk_ssfha_surgeonly.yaml` | Surge-only SS-FHA config |
| `cases/norfolk_ssfha_comparison/norfolk_triton_only.yaml` | TRITON-only config |
| `cases/norfolk_ssfha_comparison/norfolk_design_storm_bds.yaml` | Basic design storm comparison config |

### Modified Files

| File | Change |
|------|--------|
| `docs/planning/active/refactors/full_codebase_refactor/work_chunks/README.md` | Add 00 to status table |
| `docs/planning/active/refactors/full_codebase_refactor/full_codebase_refactor.md` | Update Phase 0 section; note decisions made and gaps found |
| `docs/planning/active/refactors/full_codebase_refactor/work_chunks/01D_io_layer.md` | Add note about raw vs. clipped geospatial file decision |
| `docs/planning/active/refactors/full_codebase_refactor/work_chunks/01B_pydantic_config_model.md` | Add smoke test to Definition of Done: load each case study YAML from `cases/norfolk_ssfha_comparison/` |

---

## Risks and Edge Cases

| Risk | Mitigation |
|------|-----------|
| YAML schema changes in 01B make these YAMLs invalid | Header comment on each YAML; 01B DoD includes loading them as smoke tests |
| Missing files block Phase 6 | Every gap is `# TODO: missing` in YAML and in the data tracking checklist above |
| Decision on raw vs. clipped files deferred | Make it here — deferring causes 01D to be designed blind |
| `fha_id` strings chosen here collide with Snakemake wildcard constraints | Keep IDs alphanumeric + underscores only; no spaces or special characters |

---

## Validation

No automated tests. Human review:

- [ ] Each YAML passes `python -c "import yaml; yaml.safe_load(open('...'))"` without error
- [ ] Each YAML has a provisional-schema header comment
- [ ] README lists all data gaps with clear status and action items
- [ ] Every decision in "Decisions to Make" is addressed and documented

---

## Definition of Done

- [ ] `cases/norfolk_ssfha_comparison/README.md` created
- [ ] `cases/norfolk_ssfha_comparison/norfolk_study_area.yaml` created
- [ ] `cases/norfolk_ssfha_comparison/norfolk_ssfha_compound.yaml` created (primary config)
- [ ] `cases/norfolk_ssfha_comparison/norfolk_ssfha_rainonly.yaml` created
- [ ] `cases/norfolk_ssfha_comparison/norfolk_ssfha_surgeonly.yaml` created
- [ ] `cases/norfolk_ssfha_comparison/norfolk_triton_only.yaml` created
- [ ] `cases/norfolk_ssfha_comparison/norfolk_design_storm_bds.yaml` created
- [ ] All 5 Decisions documented in README or YAML comments
- [ ] All data tracking checklist items have status and action assigned
- [ ] Each YAML passes `yaml.safe_load()` without error
- [ ] `full_codebase_refactor.md` Phase 0 section updated
- [ ] `01B` and `01D` planning docs updated with relevant notes from decisions made here
- [ ] **Move this document to `implemented/` once all boxes above are checked**
