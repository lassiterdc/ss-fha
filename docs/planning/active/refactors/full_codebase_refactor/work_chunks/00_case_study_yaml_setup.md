# Work Chunk 00: Case Study YAML Setup

**Phase**: 0 — Pre-Implementation (Config and Data Inventory)
**Last edited**: 2026-02-25 (decisions recorded 2026-02-25)

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

All SS zarrs share the same clean structure: dims `(x: 526, y: 513, event_iloc: 3798)`, single data variable `max_wlevel_m`, coordinates `x`, `y`, `event_iloc` only. Scalar metadata coordinates (e.g., `ensemble_type`, `simtype`) have been dropped from the zarrs — the simulation type is encoded in the filename instead. Inspected and confirmed 2026-02-25.

| File | Description | Dims / Coords | Status |
|------|-------------|---------------|--------|
| `ss_tritonswmm_combined.zarr` | SS combined (rain + surge) simulation peak flood depths (TRITON+SWMM coupled) | `(x:526, y:513, event_iloc:3798)` | ✓ Present |
| `ss_tritonswmm_rainonly.zarr` | SS rain-only simulation peak flood depths | `(x:526, y:513, event_iloc:3798)` | ✓ Present |
| `ss_tritonswmm_surgeonly.zarr` | SS surge-only simulation peak flood depths | `(x:526, y:513, event_iloc:3798)` | ✓ Present |
| `ss_triton_only_combined.zarr` | SS TRITON-only (no SWMM coupling) peak flood depths — combined drivers | `(x:526, y:513, event_iloc:3798)` | ✓ Present |
| `design_storm_tritonswmm_combined.zarr` | Design storm combined peak flood depths | `(return_pd_yrs:4, x:526, y:513)` — `return_pd_yrs=[1,2,10,100]` | ✓ Present |
| `design_storm_tritonswmm_rainonly.zarr` | Design storm rain-only peak flood depths | `(return_pd_yrs:4, x:526, y:513)` | ✓ Present |
| `design_storm_tritonswmm_surgeonly.zarr` | Design storm surge-only peak flood depths | `(return_pd_yrs:4, x:526, y:513)` | ✓ Present |
| `obs_tritonswmm_combined.zarr` | Observed event peak flood depths — needed for PPCCT (Workflow 3) | `(x:526, y:513, event_iloc:71)` — confirmed matches SS zarr grid | ✓ Present |

**Note on design storm zarr structure**: The design storm zarrs are indexed by `return_pd_yrs=[1,2,10,100]` (not `event_iloc`), reflecting that each design storm *is* a return-period event, not a member of the stochastic ensemble. The `(x: 526, y: 513)` grid is identical to the SS zarrs. The 24-hr rain duration applies to the combined design storm; the surge-only design storm uses a 6-hr duration (confirmed from time series analysis). Metadata about model type and rain duration is not embedded in the zarr — it is captured in the YAML config.

**Note on "combined" vs "compound" terminology**: Throughout this codebase, "combined" refers to simulations that include *both* rainfall and storm tide as flood drivers. "Compound" is reserved for flooding that is worsened by the simultaneous presence of multiple drivers — a phenomenon description, not a simulation type. This distinction is documented in `.prompts/philosophy.md`. Zarr filenames use "combined" consistently. The upstream source zarr used `ensemble_type='compound'`; that coordinate has been dropped.

### `events/` — Event summaries and time series

| File | Description | Shape / Dims | Status |
|------|-------------|-------------|--------|
| `ss_simulation_summaries.csv` | Per-event meteorological summaries for all 3,798 SS simulations. Includes event type (combined/rain/surge — upstream labels in CSV may use "compound" for the combined type), rescaling parameters, observed event linkages, and ~40 rainfall/surge intensity statistics. | `(3798, 40)` | ✓ Present |
| `ss_event_iloc_mapping.csv` | Maps flat `event_number` (0–3797) to `(year, event_type, event_id)` — the 3D index used in time series NetCDFs. Essential for linking zarr `event_iloc` to event metadata. | `(3798, 4)` cols: `event_number, year, event_type, event_id` | ✓ Present |
| `ss_simulation_time_series.nc` | Per-event time series for all SS simulations: rainfall intensity, water level, surge, tide, plus 6 rain gage IDs (156, 171, 170, 155, 140, 141). `year` dim spans 954 values (not all 1000 — some years had no events). `event_id` max=5 (up to 5 events per year per type). | `(event_type=3, year=954, event_id=5, timestep=3261)` ~4 GB | ✓ Present |
| `obs_event_summaries_from_yrs_with_complete_coverage.csv` | Per-event meteorological summaries for 71 observed events from years with complete data coverage. Same intensity stat schema as SS summaries but richer (includes observed data source flags). | `(71, 61)` | ✓ Present |
| `obs_event_iloc_mapping.csv` | Maps flat `event_iloc` to `(year, event_type, event_id)` for the 71 observed events. | `(71, 4)` cols: `event_iloc, year, event_type, event_id` | ✓ Present |
| `obs_event_tseries_from_yrs_with_complete_coverage.nc` | Per-event time series for observed events. Same variables as SS time series plus `first_obs_tstep_w_rainfall`. `year` spans 18 (years with complete coverage). | `(year=18, event_type=3, event_id=5, timestep=2174)` ~47 MB | ✓ Present |
| `design_storm_combined.nc` | Design storm time series for combined (rain + surge) storms. `year` dim = 4, representing the 4 return periods [1, 2, 10, 100 yr]. Same variables as SS time series. | `(year=4, timestep=336)` | ✓ Present |
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

- [x] **Observed TRITON output zarr** (`obs_tritonswmm_combined.zarr`) — **RESOLVED**: staged and confirmed 2026-02-25. Dim structure: `(x:526, y:513, event_iloc:71)` — grid matches SS zarrs; 71 observed events.

*No other files are missing.* Tide gage data, empirical return period CSVs, and the AOI shapefile are not required inputs — see inventory table notes above.

### Values Requiring Confirmation

- [ ] **`n_years_synthesized: 1000`** — Record in `norfolk_ssfha_combined.yaml` (and all FHA variant YAMLs). This is the total number of synthetic years in the SS weather model run, including years with no events. The SS time series contains only 954 years (those with ≥1 event); 1000 is confirmed by `N_YEARS_SYNTHESIZED = 1000` in `__inputs.py`. This value is the denominator for all simulated return period calculations — it must be explicitly set in config and never inferred from data dimensions. See notes in 01B and 02B.

- [ ] **`n_years_observed: 18`** — Record in `norfolk_ssfha_combined.yaml`. This is the total length of the observed record. For Norfolk, all 18 observed years have ≥1 event (confirmed: `obs_ds.year` has 18 values), so `len(obs_ds.year) == n_years_observed` happens to be true here. However other case studies may have event-free observed years, so this must always be set explicitly — never inferred from data dimensions. Used as the denominator for observed return period calculations in PPCCT. See notes in 01B and 02B.

### Files Present but Requiring Verification or Decisions

- [ ] **Confirm CRS of all geospatial files** (roads, sidewalks, buildings, parcels, FEMA raster)
  - Watershed is confirmed EPSG:32147. All others need verification.
  - Action: Run `geopandas.read_file(...).crs` / `rasterio.open(...).crs` for each.

- [x] **Decide: raw vs. pre-clipped geospatial files** — **RESOLVED**: clip on load (Decision 1 below). `gis_io.read_shapefile` accepts an optional `clip_to` argument. If clipping is computationally expensive, it can be promoted to a dedicated Snakemake pre-processing rule whose output is cached and depended on by downstream rules.

- [ ] **Confirm meaning of integer variable names** (156, 171, 170, 155, 140, 141) in time series NetCDFs
  - Appear in both SS and observed time series. Likely NOAA rain gage station IDs or SWMM node IDs.
  - Action: Check TRITON-SWMM_toolkit outputs or documentation for variable naming convention. Decision point for `01D` I/O layer.

- [ ] **Confirm `N_YEARS_SYNTHESIZED`**
  - `__inputs.py` has `N_YEARS_SYNTHESIZED = 1000` but the SS time series has `year` dim = 954 (not 1000 — some years had no simulated events). The TRITON zarr has `event_iloc = 3798`. The actual count must be derived from the data, not from a hardcoded constant.
  - Action: Confirm `N_YEARS_SYNTHESIZED` is truly 1000 (and 954 is just years with ≥1 event), and that this distinction is handled correctly when computing empirical return periods.

- [x] **Confirm design storm `rain_duration_h`** — **RESOLVED**: The combined design storm uses 24-hr rain duration; the surge-only design storm uses 6-hr duration. Only the 24-hr combined storm is in scope for the BDS comparison (corroborated by `TARGET_DESIGN_STORM_DURATION_HRS_FOR_COMPARISON = 24` in `__inputs.py`). The `rain_duration_h` metadata coordinate has been dropped from the design storm zarrs (encoding in filename is sufficient); duration is documented in YAML config comments.

- [ ] **Confirm `RETURN_PERIODS` scope**
  - `__inputs.py` has `RETURN_PERIODS = [1, 2, 10, 100]` with the comment "this can't be changed because this is all that is available for the tide gage return periods." The design storm zarrs confirm `return_pd_yrs = [1, 2, 10, 100]`. This should be a default in `config/defaults.py` but users must understand it is constrained by upstream data.
  - Action: Confirm and document in `norfolk_study_area.yaml` with a clear comment about the constraint.

- [x] **`ppct_alpha` / `FLD_RTRN_PD_ALPHA` classification** — **RESOLVED** (Decision 5 below): Both are generic analysis defaults → `config/defaults.py`. `ppct_alpha = 0.05` is the standard hypothesis testing significance level. `FLD_RTRN_PD_ALPHA = 0.1` (90% CI) is chosen to match NOAA Atlas 14 — a methodological convention, not Norfolk-specific.

---

## Decisions Made

All decisions are recorded here with rationale. Relevant YAMLs and planning docs have been updated accordingly.

### Decision 1: Raw vs. pre-clipped geospatial files — **RESOLVED: clip on load**

**Context**: Roads, sidewalks, and buildings in staging are raw city-wide/statewide files. Old code used pre-clipped files.

**Decision**: Clip on load (Option A). `gis_io.read_shapefile` accepts an optional `clip_to: gpd.GeoDataFrame | None` argument that clips to the watershed polygon on read. HydroShare holds raw files — this makes the library general-purpose and avoids case-study-specific preprocessing on HydroShare.

**Performance caveat**: If clipping is computationally expensive for large files (e.g., the Virginia statewide buildings shapefile), the clip operation should be promoted to a dedicated Snakemake pre-processing rule. Downstream rules depend on that rule's output, ensuring the clip runs once and is cached. This is an `01D` implementation concern.

**Impact on 01D**: `read_shapefile` signature requires `clip_to` parameter (not a default — callers must be explicit). See `01D_io_layer.md` for the updated design note.

### Decision 2: `fha_id` naming convention — **RESOLVED**

Canonical `fha_id` strings (used as Snakemake wildcards and output directory names). All IDs are alphanumeric + underscores only.

| Config file | `fha_id` | `fha_approach` |
|-------------|----------|----------------|
| `norfolk_ssfha_combined.yaml` | `ssfha_combined` | `ssfha` |
| `norfolk_ssfha_rainonly.yaml` | `ssfha_rainonly` | `ssfha` |
| `norfolk_ssfha_surgeonly.yaml` | `ssfha_surgeonly` | `ssfha` |
| `norfolk_ssfha_triton_only_combined.yaml` | `ssfha_triton_only_combined` | `ssfha` |
| `norfolk_bds.yaml` | `bds_combined_24hr` | `bds` |

### Decision 3: MCDS scope — **RESOLVED: implement as toggle on combined SSFHA config**

**Context**: The current MCDS implementation subsets Monte Carlo design storms from within the stochastic ensemble — it reuses `ss_tritonswmm_combined.zarr` directly, with no separate model inputs. MCDS is not a fully independent FHA approach; it is a post-processing variant of the SSFHA combined run.

**Decision**: MCDS is in scope and is implemented as `toggle_mcds: bool` on the primary combined SSFHA config (`norfolk_ssfha_combined.yaml`). It does NOT get its own `fha_approach: mcds` YAML or `fha_id`, because it shares all inputs with the SSFHA combined run. The toggle triggers an additional analysis step within Phase 3E (design comparison).

**MCDS formulations in scope** (from old code): multivariate AND, multivariate OR, univariate. All three are implemented; outputs are `mcds_return_pd_floods_multivar.nc`, `mcds_return_pd_floods_multivar_OR.nc`, `mcds_return_pd_floods_univar.nc`.

**Shelved improvement**: A standalone MCDS approach (independent stochastic event generation, not subsetted from SSFHA) would require a new weather model run and simulation ensemble. This is documented as a future improvement in `full_codebase_refactor.md` but is out of scope for this refactor.

**Impact on 03E**: `design_comparison.md` must include the MCDS toggle and its three output formulations. Update when implementing 03E.

### Decision 4: `constant_head_bndry_cndtn` — **RESOLVED: not an ss-fha input**

This parameter is a fixed sea water level used in rain-only simulations within TRITON-SWMM_toolkit. It is a known input to the TRITON-SWMM simulation configuration, not to the ss-fha analysis. It does not need to appear in any ss-fha YAML. No action required.

### Decision 5: `ppct_alpha` and `FLD_RTRN_PD_ALPHA` classification — **RESOLVED: both are generic defaults**

- `ppct_alpha = 0.05`: Standard significance level for hypothesis testing → `config/defaults.py`.
- `FLD_RTRN_PD_ALPHA = 0.1`: 90% CI chosen to match NOAA Atlas 14 convention — a methodological standard, not Norfolk-specific → `config/defaults.py` with a comment citing NOAA Atlas 14.

### Decision 6: "Combined" vs. "compound" terminology — **RESOLVED**

**"Combined"** refers to simulations that include both rainfall and storm tide as flood drivers simultaneously. This is a simulation-type label.

**"Compound"** is reserved for the *phenomenon* of flooding worsened by the simultaneous presence of multiple drivers — a scientific/descriptive term, not a simulation label.

**Convention**:
- Zarr filenames: use `combined` (e.g., `ss_tritonswmm_combined.zarr`) ✓ already applied
- `fha_id` values: use `combined` (e.g., `ssfha_combined`) ✓ applied in Decision 2
- Config field names: use `combined` (e.g., `TritonOutputsConfig.combined`, not `.compound`)
- Documentation: "combined simulation" or "combined drivers", never "compound simulation"
- Scientific discussion: "compound flooding" or "compound flood hazard" remains correct usage

**Terminology updates applied** (2026-02-25):
- `full_codebase_refactor.md` ✓ — filenames, `fha_id`, `TritonOutputsConfig.combined`, Snakemake examples, sim-type args
- `01B_pydantic_config_model.md` ✓ — `TritonOutputsConfig.combined` field, smoke test dict, DoD items
- `.prompts/philosophy.md` ✓ — Terminology section added

**Upstream data note**: `_work/exporting_case_study_data_files.py` uses `event_type=["compound"]` when selecting from the source zarr. This refers to the upstream coordinate label in the original simulation results — it is acceptable to keep as-is since it reads data, not defines our naming convention. The output zarr is correctly named `ss_tritonswmm_combined.zarr`.

---

## Task Understanding

### Requirements

1. **`cases/norfolk_ssfha_comparison/norfolk_study_area.yaml`** — Norfolk-specific scalar parameters not in HydroShare and not in generic code defaults:
   - `crs_epsg: 32147` (confirmed from watershed shapefile)
   - Any other site-specific scalars identified during `__inputs.py` audit

2. **`cases/norfolk_ssfha_comparison/norfolk_ssfha_combined.yaml`** — Primary SS-FHA config (combined drivers). All paths point to the local staging directory. Includes `toggle_mcds: true` to enable Monte Carlo design storm analysis (subsets from this ensemble). Use `# TODO: missing — [description]` for absent files.

3. **`cases/norfolk_ssfha_comparison/norfolk_ssfha_rainonly.yaml`** — Rain-only SS-FHA config. Standalone YAML (no YAML anchors or inheritance).

4. **`cases/norfolk_ssfha_comparison/norfolk_ssfha_surgeonly.yaml`** — Surge-only SS-FHA config.

5. **`cases/norfolk_ssfha_comparison/norfolk_ssfha_triton_only_combined.yaml`** — TRITON-only (no SWMM coupling) config.

6. **`cases/norfolk_ssfha_comparison/norfolk_bds.yaml`** — Basic design storm comparison config (`fha_approach: bds`).

7. **`cases/norfolk_ssfha_comparison/README.md`** — Directory purpose, YAML inventory, data gap tracking, decisions made.

### YAML Schema (Provisional)

These YAMLs are written to the *intended* `SSFHAConfig` schema (defined in 01B, not yet implemented). Field names are provisional; add a header comment noting they must be validated when 01B is implemented. 01B's Definition of Done should include loading these YAMLs as a smoke test.

```yaml
# PROVISIONAL — field names subject to change when SSFHAConfig (01B) is implemented.
# Validate all fields against SSFHAConfig when 01B is complete.

fha_id: ssfha_combined
fha_approach: ssfha        # "ssfha" | "bds"
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
  combined: /mnt/d/Dropbox/_GradSchool/repos/ss-fha/hydroshare_data/model_results/ss_tritonswmm_combined.zarr
  observed: /mnt/d/Dropbox/_GradSchool/repos/ss-fha/hydroshare_data/model_results/obs_tritonswmm_combined.zarr

toggle_mcds: true  # Monte Carlo design storm analysis — subsets design storms from this ensemble.
                   # Only valid when fha_approach: ssfha. Implements multivariate AND/OR + univariate
                   # formulations. A standalone MCDS method (independent event generation) is a
                   # shelved future improvement — see full_codebase_refactor.md.

event_data:
  sim_event_summaries: /mnt/d/Dropbox/_GradSchool/repos/ss-fha/hydroshare_data/events/ss_simulation_summaries.csv
  sim_event_timeseries: /mnt/d/Dropbox/_GradSchool/repos/ss-fha/hydroshare_data/events/ss_simulation_time_series.nc
  sim_event_iloc_mapping: /mnt/d/Dropbox/_GradSchool/repos/ss-fha/hydroshare_data/events/ss_event_iloc_mapping.csv
  obs_event_summaries: /mnt/d/Dropbox/_GradSchool/repos/ss-fha/hydroshare_data/events/obs_event_summaries_from_yrs_with_complete_coverage.csv
  obs_event_timeseries: /mnt/d/Dropbox/_GradSchool/repos/ss-fha/hydroshare_data/events/obs_event_tseries_from_yrs_with_complete_coverage.nc
  obs_event_iloc_mapping: /mnt/d/Dropbox/_GradSchool/repos/ss-fha/hydroshare_data/events/obs_event_iloc_mapping.csv
  # empirical_rainfall_return_periods — not an input; written by event stats runner to output_dir/event_statistics/
  # empirical_water_level_return_periods — same as above

geospatial:
  watershed: /mnt/d/Dropbox/_GradSchool/repos/ss-fha/hydroshare_data/geospatial/norfolk_wshed_epsg32147_state_plane_m.shp
  roads: /mnt/d/Dropbox/_GradSchool/repos/ss-fha/hydroshare_data/geospatial/Street_Centerline_-_City_of_Norfolk.shp  # raw city-wide; clipped to watershed on load
  sidewalks: /mnt/d/Dropbox/_GradSchool/repos/ss-fha/hydroshare_data/geospatial/Sidewalk_-_City_of_Norfolk.shp       # raw city-wide; clipped on load
  buildings: /mnt/d/Dropbox/_GradSchool/repos/ss-fha/hydroshare_data/geospatial/buildings_from_ms_github/va_buildings.shp  # raw statewide; clipped on load
  parcels: /mnt/d/Dropbox/_GradSchool/repos/ss-fha/hydroshare_data/geospatial/Parcel_Boundaries/Parcel_Boundaries.shp
  fema_100yr_depths: /mnt/d/Dropbox/_GradSchool/repos/ss-fha/hydroshare_data/geospatial/fema/100yr_depths_m.tif
  # No aoi.shp — spatial subsetting uses the watershed shapefile directly.

execution:
  mode: local_concurrent
  max_workers: 4

toggle_uncertainty: true
toggle_ppcct: true
toggle_flood_risk: true
toggle_design_comparison: true

alt_fha_analyses:
  - cases/norfolk_ssfha_comparison/norfolk_ssfha_rainonly.yaml
  - cases/norfolk_ssfha_comparison/norfolk_ssfha_surgeonly.yaml
  - cases/norfolk_ssfha_comparison/norfolk_ssfha_triton_only_combined.yaml
  - cases/norfolk_ssfha_comparison/norfolk_bds.yaml
```

---

## File-by-File Change Plan

### New Files

| File | Purpose |
|------|---------|
| `cases/norfolk_ssfha_comparison/README.md` | Directory purpose, YAML inventory, data gaps, decisions |
| `cases/norfolk_ssfha_comparison/norfolk_study_area.yaml` | Norfolk-specific scalar parameters (EPSG, etc.) |
| `cases/norfolk_ssfha_comparison/norfolk_ssfha_combined.yaml` | Primary SS-FHA config (combined drivers) with `toggle_mcds: true` and local staging paths |
| `cases/norfolk_ssfha_comparison/norfolk_ssfha_rainonly.yaml` | Rain-only SS-FHA config |
| `cases/norfolk_ssfha_comparison/norfolk_ssfha_surgeonly.yaml` | Surge-only SS-FHA config |
| `cases/norfolk_ssfha_comparison/norfolk_ssfha_triton_only_combined.yaml` | TRITON-only (no SWMM coupling) config |
| `cases/norfolk_ssfha_comparison/norfolk_bds.yaml` | Basic design storm comparison config (`fha_approach: bds`) |

### Modified Files

| File | Change |
|------|--------|
| `docs/planning/active/refactors/full_codebase_refactor/work_chunks/README.md` | Add 00 to status table |
| `docs/planning/active/refactors/full_codebase_refactor/full_codebase_refactor.md` | Update Phase 0 section; update filenames, terminology, MCDS design, TritonOutputsConfig field names |
| `docs/planning/active/refactors/full_codebase_refactor/work_chunks/01D_io_layer.md` | Add note about raw vs. clipped decision and `clip_to` parameter design |
| `docs/planning/active/refactors/full_codebase_refactor/work_chunks/01B_pydantic_config_model.md` | Update `TritonOutputsConfig.compound` → `.combined`; add MCDS toggle field; add smoke test to DoD |
| `.prompts/philosophy.md` | Add Terminology section defining combined vs. compound |

---

## Risks and Edge Cases

| Risk | Mitigation |
|------|-----------|
| YAML schema changes in 01B make these YAMLs invalid | Header comment on each YAML; 01B DoD includes loading them as smoke tests |
| Missing files block Phase 6 | Every remaining gap is noted in the data tracking checklist with a clear action |
| `fha_id` strings collide with Snakemake wildcard constraints | All IDs confirmed alphanumeric + underscores only; no spaces or special characters |
| MCDS toggle silently skipped if `fha_approach != ssfha` | 01B validator must raise `ConfigurationError` if `toggle_mcds=True` on a non-ssfha config |

---

## Validation

No automated tests. Human review:

- [ ] Each YAML passes `python -c "import yaml; yaml.safe_load(open('...'))"` without error
- [ ] Each YAML has a provisional-schema header comment
- [ ] README lists all data gaps with clear status and action items
- [ ] All decisions in "Decisions Made" are documented with rationale

---

## Definition of Done

- [ ] `cases/norfolk_ssfha_comparison/README.md` created
- [ ] `cases/norfolk_ssfha_comparison/norfolk_study_area.yaml` created
- [ ] `cases/norfolk_ssfha_comparison/norfolk_ssfha_combined.yaml` created (primary config, with `toggle_mcds: true`)
- [ ] `cases/norfolk_ssfha_comparison/norfolk_ssfha_rainonly.yaml` created
- [ ] `cases/norfolk_ssfha_comparison/norfolk_ssfha_surgeonly.yaml` created
- [ ] `cases/norfolk_ssfha_comparison/norfolk_ssfha_triton_only_combined.yaml` created
- [ ] `cases/norfolk_ssfha_comparison/norfolk_bds.yaml` created
- [ ] All 6 Decisions documented in this file
- [ ] All data tracking checklist items have status and action assigned
- [ ] Each YAML passes `yaml.safe_load()` without error
- [ ] `full_codebase_refactor.md` Phase 0 section updated
- [ ] `01B` and `01D` planning docs updated with relevant notes from decisions made here
- [ ] **Move this document to `implemented/` once all boxes above are checked**
